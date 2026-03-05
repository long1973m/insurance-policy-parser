#!/usr/bin/env python3
"""
阶段二完整流水线
整合：
- Layer 1 增强版（更好的章节切分）
- Layer 2-Skill 1（数值型字段）
- Layer 2-Skill 2（逻辑类字段）
- Layer 3（增强质量控制）
"""

import json
from typing import Dict, Any
from pathlib import Path

# 导入各层组件
from layer1_enhanced import EnhancedTextPreprocessor
from layer2_skill1_numeric_extractor import NumericFieldExtractor
from layer2_skill2_logic_extractor import LogicFieldExtractor, extract_logic_fields
from layer3_quality_controller import quality_check


def run_stage2_pipeline(pdf_path: str, output_json: str = None) -> Dict[str, Any]:
    """
    执行阶段二完整抽取流水线
    
    Pipeline流程：
    Layer 1 (增强预处理) → 
    Layer 2-Skill 1 (数值型) + Layer 2-Skill 2 (逻辑类) → 
    Layer 3 (质量控制)
    """
    print("="*80)
    print("🚀 启动保险条款抽取流水线 (阶段二 - 完善版)")
    print("="*80)
    print(f"📄 输入文件: {pdf_path}")
    print()
    
    # ==================== Layer 1: 增强文本预处理 ====================
    print("📦 Layer 1: 增强文本预处理")
    print("-" * 40)
    
    try:
        preprocessor = EnhancedTextPreprocessor(pdf_path)
        sections = preprocessor.preprocess()
        full_text = preprocessor.full_text
        
        print(f"✅ 预处理完成")
        print(f"   - 总页数: {len(preprocessor.reader.pages)}")
        print(f"   - 识别章节: {len(sections)}个")
        print(f"   - 总字符数: {len(full_text):,}")
        
        # 显示关键章节
        key_sections = ['保险责任', '续保条款', '投保规则', '免赔额']
        print(f"\n   📑 关键章节:")
        for key in key_sections:
            if key in sections:
                sec = sections[key]
                print(f"      ✅ {key}: {sec.start_page}-{sec.end_page}页 ({len(sec.text):,}字符)")
            else:
                # 尝试模糊匹配
                found = False
                for name, sec in sections.items():
                    if key in name or name in key:
                        print(f"      ✅ {key}→{name}: {sec.start_page}-{sec.end_page}页")
                        found = True
                        break
                if not found:
                    print(f"      ❌ {key}: 未找到")
        
    except Exception as e:
        print(f"❌ Layer 1 失败: {str(e)}")
        return {'error': f'文本预处理失败: {str(e)}'}
    
    print()
    
    # ==================== Layer 2: 字段抽取 ====================
    print("🔢 Layer 2: 字段抽取")
    print("-" * 40)
    
    all_results = {}
    
    # Skill 1: 数值型字段
    print("\n   Skill 1: 数值型字段")
    try:
        numeric_extractor = NumericFieldExtractor(full_text)
        numeric_results = numeric_extractor.extract_all()
        
        for field_name, result in numeric_results.items():
            all_results[field_name] = {
                'value': result.value,
                'source_text': result.source_text,
                'confidence': result.confidence,
                'extractor_type': result.extractor_type,
                'skill': 'numeric'
            }
        
        numeric_summary = numeric_extractor.get_extraction_summary()
        print(f"   ✅ 完成: {numeric_summary['extracted_count']}/{numeric_summary['total_fields']} 字段")
        
    except Exception as e:
        print(f"   ❌ 失败: {str(e)}")
    
    # Skill 2: 逻辑类字段
    print("\n   Skill 2: 逻辑类字段")
    try:
        # 准备章节字典
        sections_dict = {name: sec.text for name, sec in sections.items()}
        logic_extractor = LogicFieldExtractor(full_text, sections_dict)
        logic_results = logic_extractor.extract_all()
        
        for field_name, result in logic_results.items():
            all_results[field_name] = {
                'value': result.value,
                'source_text': result.source_text,
                'confidence': result.confidence,
                'priority': result.priority.name,
                'reasoning': result.reasoning,
                'skill': 'logic'
            }
        
        logic_extracted = sum(1 for r in logic_results.values() if r.value is not None)
        print(f"   ✅ 完成: {logic_extracted}/{len(logic_results)} 字段")
        
        # 检测逻辑冲突
        conflicts = logic_extractor.detect_conflicts()
        if conflicts:
            print(f"   ⚠️  检测到 {len(conflicts)} 个逻辑冲突")
        
    except Exception as e:
        print(f"   ❌ 失败: {str(e)}")
    
    # 显示关键字段
    print(f"\n   🎯 关键字段值:")
    key_fields = [
        ('deductible_amount', '免赔额'),
        ('waiting_period_days', '等待期'),
        ('reimbursement_ratio_with_social_security', '有社保赔付比例'),
        ('renewal_guaranteed', '保证续保'),
        ('renewal_guarantee_years', '保证续保年限'),
    ]
    
    for field_key, field_label in key_fields:
        data = all_results.get(field_key, {})
        value = data.get('value')
        conf = data.get('confidence', 0)
        skill = data.get('skill', '?')
        
        status = "✅" if value is not None else "❌"
        print(f"      {status} {field_label}({field_key}): {value}")
        print(f"         [置信度:{conf:.2f}, 技能:{skill}]")
    
    print()
    
    # ==================== Layer 3: 质量控制 ====================
    print("🔍 Layer 3: 质量控制")
    print("-" * 40)
    
    try:
        quality_report = quality_check(all_results)
        
        print(f"✅ 质量检查完成")
        print(f"   - 质量评分: {quality_report['quality_score']:.2f}/1.0")
        print(f"   - 整体置信度: {quality_report['confidence']:.2f}")
        print(f"   - 需要审核: {'⚠️ 是' if quality_report['needs_review'] else '✓ 否'}")
        print(f"   - 发现问题: {len(quality_report['conflicts'])}个")
        
        # 显示严重问题
        critical_high = [c for c in quality_report['conflicts'] 
                        if c['severity'] in ['critical', 'high']]
        if critical_high:
            print(f"\n   ⚠️  严重问题:")
            for i, conflict in enumerate(critical_high[:3], 1):
                print(f"      {i}. [{conflict['severity'].upper()}] {conflict['message']}")
        
    except Exception as e:
        print(f"❌ 质量检查失败: {str(e)}")
        quality_report = {'error': str(e)}
    
    print()
    
    # ==================== 组装最终结果 ====================
    final_result = {
        'pipeline_version': 'Stage2-v2.0',
        'input_file': Path(pdf_path).name,
        'layer1_preprocessing': {
            'success': True,
            'total_pages': len(preprocessor.reader.pages),
            'total_sections': len(sections),
            'total_chars': len(full_text),
            'sections_found': list(sections.keys())[:20]  # 只保留前20个
        },
        'layer2_extraction': {
            'success': True,
            'fields': all_results,
            'summary': {
                'total_fields': len(all_results),
                'numeric_fields': sum(1 for f in all_results.values() if f.get('skill') == 'numeric'),
                'logic_fields': sum(1 for f in all_results.values() if f.get('skill') == 'logic'),
            }
        },
        'layer3_quality': quality_report,
        'final_output': {
            'quality_score': quality_report.get('quality_score', 0),
            'needs_review': quality_report.get('needs_review', True),
            'recommended_action': 'MANUAL_REVIEW' if quality_report.get('needs_review') else 'AUTO_APPROVE'
        }
    }
    
    # 保存到文件
    if output_json:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存: {output_json}")
    
    print()
    print("="*80)
    print("✅ 流水线执行完成！")
    print("="*80)
    
    return final_result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python pipeline_stage2.py <pdf文件> [输出json文件]")
        print("示例: python pipeline_stage2.py policy.pdf stage2_result.json")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "stage2_result.json"
    
    result = run_stage2_pipeline(pdf_path, output)
    
    # 打印最终摘要
    print("\n📋 最终摘要:")
    print(f"   产品: {Path(pdf_path).stem}")
    print(f"   章节: {result['layer1_preprocessing']['total_sections']}个")
    print(f"   字段: {result['layer2_extraction']['summary']['total_fields']}个")
    print(f"   质量: {result['layer3_quality'].get('quality_score', 0):.2f}/1.0")
    print(f"   建议: {result['final_output']['recommended_action']}")
