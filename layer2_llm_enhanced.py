#!/usr/bin/env python3
"""
LLM 增强版字段抽取器
当规则匹配失败时，用 LLM 语义理解重试
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class LLMEnhancedExtractor:
    """LLM 增强版抽取器"""
    
    def __init__(self, full_text: str):
        self.full_text = full_text
    
    def prepare_llm_prompt(self, field_name: str, failed_context: str) -> str:
        """准备 LLM 提示词"""
        
        prompts = {
            'deductible_amount': """
从以下保险条款文本中提取"免赔额"信息：

要求：
1. 找出所有提到"免赔额"、"免赔"、"个人承担"的句子
2. 如果有明确数字（如"10000 元"），提取数字
3. 如果没有明确数字，但说"在本合同中载明"或"约定的"，说明这是"约定值"
4. 如果找到"60%"、"100%"等比例词在免赔额上下文中，可能是免赔额后的赔付比例

文本片段：
{context}

返回 JSON 格式：
{{
  "value": "数字或'约定'或 null",
  "source": "原文引用",
  "confidence": 0.0-1.0,
  "note": "说明"
}}
""",
            
            'waiting_period_days': """
从以下保险条款文本中提取"等待期"天数：

要求：
1. 找"等待期 X 天"、"等待期为 X 日"等明确表述
2. 如果只说"等待期（释义 X）"，查找释义部分的天数
3. 如果找不到，返回 null

文本片段：
{context}

返回 JSON 格式：
{{
  "value": "数字或 null",
  "source": "原文引用",
  "confidence": 0.0-1.0
}}
""",
            
            'reimbursement_ratio': """
从以下保险条款文本中提取"赔付比例"：

要求：
1. 找"X%"、"按 X% 给付"、"给付比例为 X%"
2. 区分"经社保"和"未经社保"的比例
3. 如果只说"约定的给付比例"，说明这是"约定值"

文本片段：
{context}

返回 JSON 格式：
{{
  "value": "X% 或'约定'或 null",
  "source": "原文引用",
  "confidence": 0.0-1.0,
  "type": "with_social_security|without_social_security|general"
}}
""",
            
            'total_annual_limit': """
从以下保险条款文本中提取"年度总限额/保险金额"：

要求：
1. 找"保险金额 X 万元"、"最高赔付 X 元"、"限额 X"
2. 如果只说"在本合同中载明"，说明这是"约定值"
3. 注意区分不同责任的保险金额（可能分项）

文本片段：
{context}

返回 JSON 格式：
{{
  "value": "数字或'约定'或 null",
  "source": "原文引用",
  "confidence": 0.0-1.0
}}
"""
        }
        
        return prompts.get(field_name, "").format(context=failed_context[:2000])
    
    def extract_with_llm(self, field_name: str, context: str) -> Dict:
        """
        用 LLM 抽取字段
        
        注意：这里需要调用实际的 LLM API
        现在返回一个模拟结果，实际使用时替换为真实调用
        """
        
        # 预处理：移除换行符，让文本连续（PDF 提取的文本经常有换行）
        context = re.sub(r'\s+', ' ', context).strip()
        
        # 模拟 LLM 调用（实际应该调用 OpenAI/Qwen/DeepSeek 等）
        # 这里我们用规则 + 启发式方法模拟 LLM 的行为
        
        if field_name == 'deductible_amount':
            # 1. 先找最明确的"年度免赔额为 X 万元"（人保健康格式）
            # 允许数字和单位之间有空格（PDF 提取常见问题）
            # 注意：交替顺序很重要，"万元"必须在"万"前面（更长的先匹配）
            explicit_match = re.search(r'年度免赔额\s*为\s*(\d+)\s*(万元 | 万 | 元)', context)
            
            if explicit_match:
                value_str = explicit_match.group(1)
                unit = explicit_match.group(2)
                
                if '万' in unit:
                    value = int(value_str) * 10000
                else:
                    value = int(value_str)
                
                return {
                    'value': value,
                    'source': explicit_match.group(0),
                    'confidence': 0.95,
                    'note': '从明确表述中提取'
                }
            
            # 2. 找"约定的免赔额" + 附近有数字
            if '约定的免赔额' in context or '约定的免赔' in context:
                # 在"约定的免赔额"前后 200 字内找数字
                idx = context.find('约定的免赔额') if '约定的免赔额' in context else context.find('约定的免赔')
                if idx >= 0:
                    nearby_context = context[max(0, idx-200):min(len(context), idx+200)]
                    num_match = re.search(r'([1-9]\d{0,3})\s*(万 | 万元 | 元)', nearby_context)
                    if num_match:
                        value_str = num_match.group(1)
                        unit = num_match.group(2)
                        
                        if '万' in unit:
                            value = int(value_str) * 10000
                        else:
                            value = int(value_str)
                        
                        return {
                            'value': value,
                            'source': nearby_context[:100],
                            'confidence': 0.7,
                            'note': '从"约定的免赔额"附近提取'
                        }
                
                # 没找到数字
                return {
                    'value': '约定',
                    'source': '条款中说明免赔额由投保人与保险人约定',
                    'confidence': 0.8,
                    'note': '免赔额在保险单中载明，不在条款中'
                }
            
            # 3. 找"扣除...免赔额后"
            deduct_match = re.search(r'扣除 [^\n]{0,100}?免赔额', context)
            if deduct_match:
                return {
                    'value': '约定',
                    'source': deduct_match.group(0),
                    'confidence': 0.7,
                    'note': '条款提到免赔额，但具体数字在保险单中'
                }
        
        elif field_name == 'waiting_period_days':
            # 找"等待期（释义 X）"
            ref_match = re.search(r'等待 [期期间]（释义 ([一二三四五六七八九十零\d]+)）', context)
            if ref_match:
                # 尝试查找释义部分
                definition_num = ref_match.group(1)
                
                # 找释义部分
                definition_pattern = rf'释义 [^\n]*{definition_num}[^\n]*[:：][^\n]*(\d+)[^\n]*(天 | 日)'
                def_match = re.search(definition_pattern, context)
                
                if def_match:
                    days = int(def_match.group(1))
                    return {
                        'value': days,
                        'source': def_match.group(0),
                        'confidence': 0.8
                    }
                else:
                    return {
                        'value': None,
                        'source': f'等待期（释义{definition_num}）- 需查看释义部分',
                        'confidence': 0.3,
                        'note': '等待期天数在释义部分，但未在当前文本中找到'
                    }
            
            # 找"X 天为等待期"（人保健康格式）
            days_match2 = re.search(r'([\d]+)[\s]*天为等待期', context)
            if days_match2:
                return {
                    'value': int(days_match2.group(1)),
                    'source': days_match2.group(0),
                    'confidence': 0.9
                }
            
            # 直接找"等待期 X 天"
            days_match = re.search(r'等待 [期期间][为是：:]*([\d]+)[\s]*(天 | 日)', context)
            if days_match:
                return {
                    'value': int(days_match.group(1)),
                    'source': days_match.group(0),
                    'confidence': 0.9
                }
        
        elif field_name == 'reimbursement_ratio':
            # 先找"赔付比例为 X%"（人保健康格式）
            explicit_match = re.search(r'赔付比例\s*为\s*([\d]+)%', context)
            
            if explicit_match:
                return {
                    'value': f"{explicit_match.group(1)}%",
                    'source': explicit_match.group(0),
                    'confidence': 0.95,
                    'type': 'general'
                }
            
            # 找明确的百分比
            percent_matches = re.findall(r'([\d]+)%', context)
            
            if percent_matches:
                # 找上下文区分有社保/无社保
                if '经社会医疗' in context or '经社保' in context:
                    return {
                        'value': f"{percent_matches[0]}%",
                        'source': context[:100],
                        'confidence': 0.8,
                        'type': 'with_social_security'
                    }
                elif '未经社会医疗' in context or '未经社保' in context:
                    return {
                        'value': f"{percent_matches[0]}%",
                        'source': context[:100],
                        'confidence': 0.8,
                        'type': 'without_social_security'
                    }
                else:
                    # 一般性比例
                    return {
                        'value': f"{percent_matches[0]}%",
                        'source': context[:100],
                        'confidence': 0.6,
                        'type': 'general'
                    }
            
            # 找"60%"（众安条款中有这个）
            sixty_percent = re.search(r'60%', context)
            if sixty_percent:
                return {
                    'value': '60%',
                    'source': sixty_percent.group(0),
                    'confidence': 0.5,
                    'type': 'special_case',
                    'note': '可能是特定情况下的赔付比例（如特定药品）'
                }
            
            # 找"约定的给付比例"
            if '约定的给付比例' in context or '约定给付比例' in context:
                return {
                    'value': '约定',
                    'source': '条款中说明赔付比例由投保人与保险人约定',
                    'confidence': 0.8,
                    'type': 'general',
                    'note': '赔付比例在保险单中载明，不在条款中'
                }
        
        elif field_name == 'total_annual_limit':
            # 找"保险金额"
            if '保险金额' in context:
                # 尝试找具体数字
                amount_match = re.search(r'保险金额 [为是：:]*([1-9]\d{0,3}[万]?)[\s]*(元 | 万元)?', context)
                
                if amount_match:
                    value_str = amount_match.group(1)
                    unit = amount_match.group(2) or ''
                    
                    if '万' in unit or '万' in value_str:
                        value = int(value_str.replace('万', '')) * 10000
                    else:
                        value = int(value_str)
                    
                    return {
                        'value': value,
                        'source': amount_match.group(0),
                        'confidence': 0.7
                    }
                else:
                    return {
                        'value': '约定',
                        'source': '条款中说明保险金额由投保人与保险人约定',
                        'confidence': 0.8,
                        'note': '保险金额在保险单中载明，不在条款中'
                    }
        
        # 默认：没找到
        return {
            'value': None,
            'source': '',
            'confidence': 0.0
        }


def run_llm_enhanced_extraction(full_text: str) -> Dict[str, Dict]:
    """运行 LLM 增强版抽取"""
    
    print("\n🤖 LLM 增强版字段抽取")
    print("-" * 40)
    
    extractor = LLMEnhancedExtractor(full_text)
    
    fields = {}
    
    # 抽取各字段
    for field_name in ['deductible_amount', 'waiting_period_days', 'reimbursement_ratio_with_social_security', 
                       'reimbursement_ratio_without_social_security', 'total_annual_limit']:
        
        # 简化：所有字段都用同一个上下文
        result = extractor.extract_with_llm(field_name, full_text)
        
        fields[field_name] = {
            'value': result.get('value'),
            'source_text': result.get('source', ''),
            'confidence': result.get('confidence', 0.0),
            'skill': 'llm_enhanced',
            'note': result.get('note', '')
        }
        
        # 打印结果
        status = "✅" if result.get('value') else "❌"
        value_display = result.get('value') if result.get('value') else 'None'
        print(f"   {status} {field_name}: {value_display}")
        if result.get('note'):
            print(f"      说明：{result['note']}")
    
    return fields


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    from layer1_enhanced_v2 import run_layer1_preprocessing
    
    if len(sys.argv) < 2:
        print("用法：python layer2_llm_enhanced.py <pdf 文件>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # 先运行 Layer 1
    layer1_result = run_layer1_preprocessing(pdf_path)
    
    # 合并所有章节文本
    full_text = "\n".join([s.get('text', '') for s in layer1_result['sections']])
    
    # 运行 LLM 增强抽取
    fields = run_llm_enhanced_extraction(full_text)
    
    # 打印汇总
    print(f"\n📊 抽取汇总:")
    found = sum(1 for f in fields.values() if f['value'] is not None)
    print(f"   找到 {found}/{len(fields)} 个字段")
