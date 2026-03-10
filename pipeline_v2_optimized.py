#!/usr/bin/env python3
"""
保险条款抽取流水线 v2（优化版）
整合改进：
1. Layer 1 v2 - 增强章节识别
2. Layer 1 质量检查 - PDF 质量评估
3. Layer 2 规则抽取 v2 - 更多关键词变体
4. Layer 2 LLM 增强 - 语义理解
5. 智能报告生成
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from layer1_enhanced_v2 import run_layer1_preprocessing
from layer2_llm_enhanced import run_llm_enhanced_extraction


def run_optimized_pipeline(pdf_path: str, output_path: str = None) -> dict:
    """运行优化版流水线"""
    
    print("=" * 80)
    print("🚀 保险条款抽取流水线 v2（优化版）")
    print("=" * 80)
    print(f"📄 输入文件：{pdf_path}")
    print()
    
    result = {
        'pipeline_version': 'v2-optimized',
        'timestamp': datetime.now().isoformat(),
        'input_file': pdf_path,
        'layer1_preprocessing': None,
        'layer2_extraction': None,
        'layer3_quality': None,
        'summary': None
    }
    
    # ========== Layer 1: 文本预处理 ==========
    layer1_result = run_layer1_preprocessing(pdf_path)
    result['layer1_preprocessing'] = layer1_result
    
    print()
    
    # ========== Layer 2: 字段抽取 ==========
    # 合并所有章节文本
    full_text = "\n".join([s.get('text', '') for s in layer1_result['sections']])
    
    # 运行 LLM 增强抽取
    layer2_result = run_llm_enhanced_extraction(full_text)
    result['layer2_extraction'] = {'fields': layer2_result}
    
    print()
    
    # ========== Layer 3: 质量控制 ==========
    print("🔍 Layer 3: 质量控制")
    print("-" * 40)
    
    # 计算质量评分
    fields = layer2_result
    total_fields = len(fields)
    found_fields = sum(1 for f in fields.values() if f['value'] is not None)
    high_confidence_fields = sum(1 for f in fields.values() if f.get('confidence', 0) > 0.7)
    
    # 质量评分 = (找到字段数/总字段数) * 0.5 + (高置信度字段数/总字段数) * 0.5
    quality_score = (found_fields / total_fields * 0.5 + 
                     high_confidence_fields / total_fields * 0.5) if total_fields > 0 else 0
    
    # 检测问题
    issues = []
    critical_fields = ['deductible_amount', 'reimbursement_ratio_with_social_security', 'waiting_period_days']
    
    for field_name in critical_fields:
        field = fields.get(field_name, {})
        if field.get('value') is None:
            issues.append({
                'type': 'missing_critical_field',
                'severity': 'high',
                'field': field_name,
                'message': f"关键字段'{field_name}'缺失",
                'suggestion': '该字段对保险条款分析至关重要，可能是"约定值"（在保险单中载明）'
            })
        elif field.get('value') == '约定':
            issues.append({
                'type': 'value_is_tbd',
                'severity': 'medium',
                'field': field_name,
                'message': f"字段'{field_name}'为约定值",
                'details': field.get('note', ''),
                'suggestion': '请查看保险单（policy schedule）获取具体数值'
            })
    
    # 判断是否需要人工审核
    needs_review = len(issues) > 0 or quality_score < 0.6
    
    quality_result = {
        'quality_score': round(quality_score, 2),
        'overall_confidence': round(sum(f.get('confidence', 0) for f in fields.values()) / len(fields), 2) if fields else 0,
        'needs_review': needs_review,
        'issues_count': len(issues),
        'issues': issues,
        'recommendation': 'MANUAL_REVIEW' if needs_review else 'AUTO_APPROVED'
    }
    
    result['layer3_quality'] = quality_result
    
    print(f"✅ 质量检查完成")
    print(f"   质量评分：{quality_result['quality_score']:.2f}/1.0")
    print(f"   整体置信度：{quality_result['overall_confidence']:.2f}")
    print(f"   需要审核：{'⚠️ 是' if needs_review else '✅ 否'}")
    print(f"   发现问题：{len(issues)}个")
    
    if issues:
        print(f"\n   ⚠️ 问题列表:")
        for i, issue in enumerate(issues[:5], 1):
            print(f"      {i}. [{issue['severity'].upper()}] {issue['message']}")
            if issue.get('suggestion'):
                print(f"         建议：{issue['suggestion']}")
    
    print()
    
    # ========== 生成摘要 ==========
    print("📋 生成摘要报告")
    print("-" * 40)
    
    summary = {
        'product_name': Path(pdf_path).stem,
        'total_pages': layer1_result['total_pages'],
        'total_sections': layer1_result['total_sections'],
        'is_text_pdf': layer1_result['is_text_pdf'],
        'fields_extracted': found_fields,
        'fields_total': total_fields,
        'quality_score': quality_result['quality_score'],
        'needs_review': needs_review,
        'key_findings': []
    }
    
    # 提取关键发现
    if fields.get('deductible_amount', {}).get('value') == '约定':
        summary['key_findings'].append("免赔额：在保险单中约定（不在条款中）")
    elif fields.get('deductible_amount', {}).get('value'):
        summary['key_findings'].append(f"免赔额：{fields['deductible_amount']['value']}")
    
    if fields.get('renewal_guaranteed', {}).get('value') is False:
        summary['key_findings'].append("续保条件：不保证续保")
    elif fields.get('renewal_guaranteed', {}).get('value') is True:
        summary['key_findings'].append(f"续保条件：保证续保")
    
    if fields.get('total_annual_limit', {}).get('value') == '约定':
        summary['key_findings'].append("保险金额：在保险单中约定（不在条款中）")
    
    result['summary'] = summary
    
    print(f"✅ 摘要生成完成")
    print(f"   产品：{summary['product_name']}")
    print(f"   页数：{summary['total_pages']}")
    print(f"   字段：{summary['fields_extracted']}/{summary['fields_total']}")
    print(f"   质量：{summary['quality_score']:.2f}/1.0")
    
    if summary['key_findings']:
        print(f"\n   关键发现:")
        for finding in summary['key_findings']:
            print(f"   - {finding}")
    
    print()
    
    # ========== 保存结果 ==========
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存：{output_path}")
        print()
    
    # ========== 打印最终报告 ==========
    print("=" * 80)
    print("✅ 流水线执行完成！")
    print("=" * 80)
    
    # 打印自然语言报告
    print("\n" + "=" * 80)
    print("📊 保险条款分析报告")
    print("=" * 80)
    
    print(f"\n📄 产品：{summary['product_name']}")
    print(f"📊 解析质量：{quality_result['quality_score']:.2f}/1.0")
    print(f"{'⚠️ 建议人工审核' if needs_review else '✅ 质量良好'}")
    
    print(f"\n💰 核心字段:")
    for field_name, field in fields.items():
        value = field.get('value')
        conf = field.get('confidence', 0)
        
        if value is not None:
            icon = "✅" if conf > 0.7 else "⚠️" if conf > 0.4 else "❌"
            value_display = str(value) if not isinstance(value, bool) else ("是" if value else "否")
            
            field_name_cn = {
                'deductible_amount': '免赔额',
                'deductible_unit': '免赔额单位',
                'waiting_period_days': '等待期',
                'reimbursement_ratio_with_social_security': '有社保赔付比例',
                'reimbursement_ratio_without_social_security': '无社保赔付比例',
                'total_annual_limit': '年度总限额',
                'renewal_guaranteed': '保证续保'
            }.get(field_name, field_name)
            
            print(f"   {icon} {field_name_cn}: {value_display}")
            if field.get('note'):
                print(f"      说明：{field['note']}")
    
    if issues:
        print(f"\n⚠️ 需要注意:")
        for issue in issues[:3]:
            print(f"   - {issue['message']}")
            if issue.get('suggestion'):
                print(f"     建议：{issue['suggestion']}")
    
    print("\n" + "=" * 80)
    
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python pipeline_v2_optimized.py <pdf 文件> [输出 json]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = run_optimized_pipeline(pdf_path, output_path)
