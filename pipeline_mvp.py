#!/usr/bin/env python3
"""
MVP 完整工作流
整合三层架构的核心功能
"""

import json
from typing import Dict, Any
from pathlib import Path

# 导入各层组件
from layer1_text_preprocessor import TextPreprocessor, preprocess_pdf
from layer2_skill1_numeric_extractor import NumericFieldExtractor, extract_numeric_fields
from layer3_quality_controller import QualityController, quality_check


def run_extraction_pipeline(pdf_path: str, output_json: str = None) -> Dict[str, Any]:
    """
    执行完整的抽取流水线（MVP版本）
    
    Pipeline流程：
    Layer 1 (文本预处理) → Layer 2-Skill 1 (数值型字段抽取) → Layer 3 (质量控制)
    
    Args:
        pdf_path: PDF文件路径
        output_json: 可选的输出JSON文件路径
        
    Returns:
        Dict: 完整的处理结果
    """
    print("="*80)
    print("🚀 启动保险条款抽取流水线 (MVP)")
    print("="*80)
    print(f"📄 输入文件: {pdf_path}")
    print()
    
    # ==================== Layer 1: 文本预处理 ====================
    print("📦 Layer 1: 文本预处理")
    print("-" * 40)
    
    try:
        preprocessor = TextPreprocessor(pdf_path)
        preprocessing_result = preprocessor.preprocess()
        
        print(f"✅ 预处理完成")
        print(f"   - 总页数: {preprocessing_result.metadata.get('total_pages', 'N/A')}")
        print(f"   - 识别章节: {len(preprocessing_result.sections)}个")
        print(f"   - 提取表格: {len(preprocessing_result.tables)}个")
        print(f"   - 总字符数: {len(preprocessing_result.raw_text):,}")
        
        # 显示识别的章节
        if preprocessing_result.sections:
            print(f"\n   📑 识别到的章节:")
            for name, section in list(preprocessing_result.sections.items())[:5]:  # 只显示前5个
                text_preview = section.text[:50].replace('\n', ' ')
                print(f"      • {name} (第{section.start_page}-{section.end_page}页): {text_preview}...")
            if len(preprocessing_result.sections) > 5:
                print(f"      ... 还有 {len(preprocessing_result.sections) - 5} 个章节")
        
    except Exception as e:
        print(f"❌ Layer 1 失败: {str(e)}")
        return {'error': f'文本预处理失败: {str(e)}'}
    
    print()
    
    # ==================== Layer 2-Skill 1: 数值型字段抽取 ====================
    print("🔢 Layer 2-Skill 1: 数值型字段抽取")
    print("-" * 40)
    
    try:
        # 使用全文进行抽取（MVP简化版）
        extractor = NumericFieldExtractor(preprocessing_result.raw_text)
        numeric_results = extractor.extract_all()
        
        # 转换为标准格式
        extraction_results = {}
        for field_name, result in numeric_results.items():
            extraction_results[field_name] = {
                'value': result.value,
                'source_text': result.source_text,
                'confidence': result.confidence,
                'extractor_type': result.extractor_type
            }
        
        # 添加摘要
        summary = extractor.get_extraction_summary()
        
        print(f"✅ 字段抽取完成")
        print(f"   - 总字段数: {summary['total_fields']}")
        print(f"   - 成功抽取: {summary['extracted_count']}个 ({summary['extraction_rate']:.1%})")
        print(f"   - 高置信度: {summary['high_confidence_count']}个")
        print(f"   - 平均置信度: {summary['average_confidence']:.2f}")
        
        # 显示关键字段
        key_fields = ['deductible_amount', 'waiting_period_days', 
                      'reimbursement_ratio_with_social_security']
        print(f"\n   🎯 关键字段值:")
        for field in key_fields:
            data = extraction_results.get(field, {})
            value = data.get('value')
            conf = data.get('confidence', 0)
            status = "✅" if value is not None else "❌"
            print(f"      {status} {field}: {value} (置信度:{conf:.2f})")
        
    except Exception as e:
        print(f"❌ Layer 2 失败: {str(e)}")
        return {'error': f'字段抽取失败: {str(e)}'}
    
    print()
    
    # ==================== Layer 3: 质量控制 ====================
    print("🔍 Layer 3: 质量控制")
    print("-" * 40)
    
    try:
        quality_report = quality_check(extraction_results)
        
        print(f"✅ 质量检查完成")
        print(f"   - 质量评分: {quality_report['quality_score']:.2f}/1.0")
        print(f"   - 整体置信度: {quality_report['confidence']:.2f}")
        print(f"   - 需要审核: {'⚠️ 是' if quality_report['needs_review'] else '✓ 否'}")
        print(f"   - 发现问题: {len(quality_report['conflicts'])}个")
        
        # 显示冲突详情
        if quality_report['conflicts']:
            print(f"\n   ⚠️  问题列表:")
            critical_high = [c for c in quality_report['conflicts'] 
                           if c['severity'] in ['critical', 'high']]
            for i, conflict in enumerate(critical_high[:3], 1):  # 只显示前3个严重问题
                print(f"      {i}. [{conflict['severity'].upper()}] {conflict['message']}")
                if conflict.get('suggestion'):
                    print(f"         💡 {conflict['suggestion']}")
        
    except Exception as e:
        print(f"❌ Layer 3 失败: {str(e)}")
        return {'error': f'质量检查失败: {str(e)}'}
    
    print()
    
    # ==================== 组装最终结果 ====================
    final_result = {
        'pipeline_version': 'MVP-v1.0',
        'input_file': Path(pdf_path).name,
        'layer1_preprocessing': {
            'success': True,
            'metadata': preprocessing_result.metadata,
            'statistics': {
                'total_pages': preprocessing_result.metadata.get('total_pages', 0),
                'total_sections': len(preprocessing_result.sections),
                'total_tables': len(preprocessing_result.tables),
                'total_chars': len(preprocessing_result.raw_text)
            },
            'sections_found': list(preprocessing_result.sections.keys())
        },
        'layer2_extraction': {
            'success': True,
            'fields': extraction_results,
            'summary': summary
        },
        'layer3_quality': quality_report,
        'final_output': {
            'quality_score': quality_report['quality_score'],
            'needs_review': quality_report['needs_review'],
            'recommended_action': 'MANUAL_REVIEW' if quality_report['needs_review'] else 'AUTO_APPROVE'
        }
    }
    
    # 保存到文件（如果指定）
    if output_json:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存: {output_json}")
    
    print()
    print("="*80)
    print("✅ 流水线执行完成！")
    print("="*80)
    
    return final_result


def quick_extract(pdf_path: str) -> Dict[str, Any]:
    """
    快速抽取函数 - 只返回核心字段
    
    Args:
        pdf_path: PDF文件路径
        
    Returns:
        Dict: 简化的抽取结果
    """
    result = run_extraction_pipeline(pdf_path)
    
    if 'error' in result:
        return result
    
    # 只返回核心信息
    return {
        'product_name': result['layer1_preprocessing']['metadata'].get('product_name'),
        'company': result['layer1_preprocessing']['metadata'].get('company'),
        'fields': {
            k: v['value'] 
            for k, v in result['layer2_extraction']['fields'].items() 
            if not k.startswith('_')
        },
        'quality_score': result['layer3_quality']['quality_score'],
        'needs_review': result['layer3_quality']['needs_review']
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python pipeline_mvp.py <pdf文件> [输出json文件]")
        print("示例: python pipeline_mvp.py policy.pdf result.json")
        print()
        print("或使用快速模式:")
        print("  python pipeline_mvp.py policy.pdf --quick")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # 检查是否是快速模式
    if '--quick' in sys.argv:
        result = quick_extract(pdf_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 正常模式
        output = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
        result = run_extraction_pipeline(pdf_path, output)
        
        # 打印最终摘要
        print("\n📋 最终摘要:")
        print(f"   产品: {result['layer1_preprocessing']['metadata'].get('product_name', 'N/A')}")
        print(f"   公司: {result['layer1_preprocessing']['metadata'].get('company', 'N/A')}")
        print(f"   质量: {result['layer3_quality']['quality_score']:.2f}/1.0")
        print(f"   建议: {result['final_output']['recommended_action']}")
