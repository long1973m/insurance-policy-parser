#!/usr/bin/env python3
"""
Layer 2 Skill 1 增强版：数值型字段抽取 v2
改进：
1. 添加更多关键词变体
2. 支持上下文语义理解
3. 改进数字提取逻辑
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class ExtractedField:
    """抽取字段"""
    value: Optional[object]
    source_text: str
    confidence: float
    skill: str
    page: int = 0


class NumericFieldExtractor:
    """数值型字段抽取器（增强版）"""
    
    # 免赔额关键词 + 上下文模式
    DEDUCTIBLE_PATTERNS = [
        # 明确金额：免赔额 10000 元
        (r'免赔 [额额]?[\s:：]*([1-9]\d{0,3}[万]?)[\s]*(元|万元)?', 'explicit'),
        # 约定的免赔额
        (r'约定的免赔 [额额]?[\s:：]*([1-9]\d{0,3}[万]?)[\s]*(元|万元)?', 'explicit'),
        # 扣除...免赔
        (r'扣除 [^\n]{0,50}?免赔 [额额]?[\s:：]*([1-9]\d{0,3}[万]?)[\s]*(元|万元)?', 'context'),
        # 个人先承担/自行承担
        (r'[个人自行] 承担 [\s:：]*([1-9]\d{0,3}[万]?)[\s]*(元|万元)?', 'implicit'),
        # 年度免赔额
        (r'年度免赔 [额额]?[\s:：]*([1-9]\d{0,3}[万]?)[\s]*(元|万元)?', 'explicit'),
    ]
    
    # 等待期关键词
    WAITING_PERIOD_PATTERNS = [
        # 等待期 X 天
        (r'等待 [期期间][\s:：]*([\d]+)[\s]*(天|日)?', 'explicit'),
        # 观察期 X 天
        (r'观察 [期期间][\s:：]*([\d]+)[\s]*(天|日)?', 'explicit'),
        # 等待期（释义 X）- 需要找释义
        (r'等待 [期期间]（释义 [一二三四五六七八九十零\d]+）', 'reference'),
    ]
    
    # 赔付比例关键词
    REIMBURSEMENT_PATTERNS = [
        # 明确比例：100%
        (r'给付比例 [为是：:]*([\d]+)%', 'explicit'),
        # 按 100% 给付
        (r'按 ([\d]+)%[\s]*(给付 | 赔付 | 报销)', 'explicit'),
        # 100% 给付
        (r'([\d]+)%[\s]*(给付 | 赔付 | 报销)', 'explicit'),
        # 社保后 100%
        (r'社保 [^\n]{0,30}?([\d]+)%', 'context'),
        # 约定的给付比例 - 需要找具体数字
        (r'约定的给付比例', 'reference'),
    ]
    
    def __init__(self, sections: List[Dict]):
        self.sections = sections
        self.full_text = "\n".join([s.get('text', '') for s in sections])
    
    def extract_with_patterns(self, patterns: List[Tuple[str, str]], field_name: str) -> ExtractedField:
        """用多个模式抽取字段"""
        
        for pattern, pattern_type in patterns:
            matches = list(re.finditer(pattern, self.full_text, re.IGNORECASE))
            
            if not matches:
                continue
            
            # 取第一个匹配
            match = matches[0]
            matched_text = match.group(0)
            
            # 提取值
            if len(match.groups()) >= 1:
                value_str = match.group(1)
                unit = match.group(2) if len(match.groups()) >= 2 else ""
                
                # 转换值
                if field_name in ['deductible_amount', 'waiting_period_days']:
                    if '万' in value_str:
                        value = int(value_str.replace('万', '')) * 10000
                    else:
                        value = int(value_str)
                    
                    if unit in ['万元']:
                        value = value * 10000
                    
                    return ExtractedField(
                        value=value,
                        source_text=matched_text,
                        confidence=0.9 if pattern_type == 'explicit' else 0.7,
                        skill='numeric_v2'
                    )
                
                elif field_name in ['reimbursement_ratio']:
                    percentage = int(value_str)
                    return ExtractedField(
                        value=f"{percentage}%",
                        source_text=matched_text,
                        confidence=0.9 if pattern_type == 'explicit' else 0.7,
                        skill='numeric_v2'
                    )
        
        # 没找到
        return ExtractedField(
            value=None,
            source_text="",
            confidence=0.0,
            skill='numeric_v2'
        )
    
    def extract_deductible(self) -> ExtractedField:
        """抽取免赔额"""
        result = self.extract_with_patterns(self.DEDUCTIBLE_PATTERNS, 'deductible_amount')
        
        # 特殊处理：如果找到"约定的免赔额"但没数字，需要查找具体值
        if result.value is None and '约定的免赔额' in self.full_text:
            # 查找上下文
            context_matches = re.finditer(r'约定的免赔额 [^\n]{0,200}', self.full_text)
            for ctx in context_matches:
                context = ctx.group(0)
                # 在上下文中找数字
                num_match = re.search(r'([1-9]\d{0,3}[万]?)[\s]*(元 | 万元)?', context)
                if num_match:
                    value_str = num_match.group(1)
                    if '万' in value_str:
                        value = int(value_str.replace('万', '')) * 10000
                    else:
                        value = int(value_str)
                    
                    return ExtractedField(
                        value=value,
                        source_text=context[:100],
                        confidence=0.6,  # 置信度较低
                        skill='numeric_v2'
                    )
        
        return result
    
    def extract_waiting_period(self) -> ExtractedField:
        """抽取等待期"""
        result = self.extract_with_patterns(self.WAITING_PERIOD_PATTERNS, 'waiting_period_days')
        
        # 如果是"等待期（释义 X）"，需要查找释义部分
        if result.value is None:
            ref_match = re.search(r'等待 [期期间]（释义 ([一二三四五六七八九十零\d]+)）', self.full_text)
            if ref_match:
                # 这里可以扩展：查找释义部分的具体天数
                # 简化处理：返回参考信息
                return ExtractedField(
                    value=None,
                    source_text=f"等待期（释义{ref_match.group(1)}）- 需查看释义部分",
                    confidence=0.3,
                    skill='numeric_v2'
                )
        
        return result
    
    def extract_reimbursement_ratio(self, with_social_security: bool = True) -> ExtractedField:
        """抽取赔付比例"""
        result = self.extract_with_patterns(self.REIMBURSEMENT_PATTERNS, 'reimbursement_ratio')
        
        # 区分有社保/无社保
        # 简化处理：如果找到多个比例，取第一个为有社保，第二个为无社保
        if result.value:
            # 检查是否有"经社保"、"未经社保"的区分
            if with_social_security:
                social_security_matches = re.finditer(r'经 [过通] 社会医疗保险 [^\n]{0,100}?([\d]+)%', self.full_text)
                for match in social_security_matches:
                    return ExtractedField(
                        value=f"{match.group(1)}%",
                        source_text=match.group(0),
                        confidence=0.85,
                        skill='numeric_v2'
                    )
            else:
                no_social_security_matches = re.finditer(r'未经社会医疗保险 [^\n]{0,100}?([\d]+)%', self.full_text)
                for match in no_social_security_matches:
                    return ExtractedField(
                        value=f"{match.group(1)}%",
                        source_text=match.group(0),
                        confidence=0.85,
                        skill='numeric_v2'
                    )
        
        return result
    
    def extract_all(self) -> Dict[str, ExtractedField]:
        """抽取所有数值型字段"""
        fields = {}
        
        # 免赔额
        fields['deductible_amount'] = self.extract_deductible()
        
        # 免赔额单位（默认年）
        fields['deductible_unit'] = ExtractedField(
            value='年',
            source_text='使用默认值：年',
            confidence=0.5,
            skill='numeric_v2'
        )
        
        # 等待期
        fields['waiting_period_days'] = self.extract_waiting_period()
        
        # 有社保赔付比例
        fields['reimbursement_ratio_with_social_security'] = self.extract_reimbursement_ratio(with_social_security=True)
        
        # 无社保赔付比例
        fields['reimbursement_ratio_without_social_security'] = self.extract_reimbursement_ratio(with_social_security=False)
        
        # 年度总限额（简化：找"保险金额"）
        limit_match = re.search(r'保险金额 [为是：:]*([1-9]\d{0,3}[万]?)[\s]*(元 | 万元)?', self.full_text)
        if limit_match:
            value_str = limit_match.group(1)
            if '万' in value_str:
                value = int(value_str.replace('万', '')) * 10000
            else:
                value = int(value_str)
            
            fields['total_annual_limit'] = ExtractedField(
                value=value,
                source_text=limit_match.group(0),
                confidence=0.7,
                skill='numeric_v2'
            )
        else:
            fields['total_annual_limit'] = ExtractedField(
                value=None,
                source_text="",
                confidence=0.0,
                skill='numeric_v2'
            )
        
        return fields


def run_numeric_extraction(sections: List[Dict]) -> Dict[str, Dict]:
    """Layer 2 Skill 1 入口函数"""
    print("\n   Skill 1: 数值型字段抽取 v2")
    print("   " + "-" * 35)
    
    extractor = NumericFieldExtractor(sections)
    fields = extractor.extract_all()
    
    # 转换为字典格式
    result = {}
    for field_name, field in fields.items():
        result[field_name] = {
            'value': field.value,
            'source_text': field.source_text,
            'confidence': field.confidence,
            'skill': field.skill
        }
        
        # 打印结果
        status = "✅" if field.value else "❌"
        print(f"   {status} {field_name}: {field.value}")
        if field.source_text and field.confidence > 0:
            preview = field.source_text[:50].replace('\n', ' ')
            print(f"      来源：...{preview}...")
    
    return result


if __name__ == "__main__":
    # 测试
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    from layer1_enhanced_v2 import run_layer1_preprocessing
    
    if len(sys.argv) < 2:
        print("用法：python layer2_skill1_numeric_v2.py <pdf 文件>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # 先运行 Layer 1
    layer1_result = run_layer1_preprocessing(pdf_path)
    
    # 再运行 Layer 2
    fields = run_numeric_extraction(layer1_result['sections'])
    
    # 打印汇总
    print(f"\n📊 抽取汇总:")
    found = sum(1 for f in fields.values() if f['value'] is not None)
    print(f"   找到 {found}/{len(fields)} 个字段")
