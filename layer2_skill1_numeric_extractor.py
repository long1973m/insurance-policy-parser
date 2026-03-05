#!/usr/bin/env python3
"""
Layer 2 - Skill 1: 数值型字段抽取
职责：抽取责任类数值字段（保额、免赔额、比例、天数等）
特点：逻辑简单，匹配规则为主
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    """抽取结果"""
    value: Any
    source_text: Optional[str]
    confidence: float = 1.0  # 置信度
    extractor_type: str = "regex"  # 抽取方式


class NumericFieldExtractor:
    """
    数值型字段抽取器
    
    抽取的字段：
    - total_annual_limit: 年度总限额
    - deductible_amount: 免赔额金额
    - deductible_unit: 免赔额单位
    - reimbursement_ratio_with_social_security: 有社保赔付比例
    - reimbursement_ratio_without_social_security: 无社保赔付比例
    - waiting_period_days: 等待期天数
    """
    
    # 字段抽取规则库
    EXTRACTION_RULES = {
        'total_annual_limit': {
            'field_type': 'amount',
            'unit': '元',
            'patterns': [
                (r'年度.*?(?:限额|保额|上限).*?(\d{1,3}(?:,\d{3})*)\s*万', '年度限额'),
                (r'最高.*?(?:赔付|给付|累计).*?(\d{1,3}(?:,\d{3})*)\s*万', '最高赔付'),
                (r'保险金额[为是：:]?\s*(\d{1,3}(?:,\d{3})*)\s*万', '保险金额'),
                (r'年度累计.*?([\d,]+)\s*万元?', '年度累计'),
            ],
            'multiplier': 10000,  # 万转元
            'validation': {'min': 500000, 'max': 10000000},  # 50万-1000万
        },
        
        'deductible_amount': {
            'field_type': 'amount',
            'unit': '元',
            'patterns': [
                (r'免赔额[是为](\d{4,})元', '免赔额为N元'),
                (r'免赔额[:：]?\s*(\d{4,})\s*元', '免赔额 N元'),
                (r'免赔额余额.*?([\d,]{4,})\s*元', '免赔额余额'),
                (r'(\d{4,})\s*元.*?(?:年[度]?)?免赔额', 'N元免赔额'),
            ],
            'multiplier': 1,
            'validation': {'min': 0, 'max': 50000},  # 0-5万
        },
        
        'deductible_unit': {
            'field_type': 'enum',
            'options': ['年', '次', '疾病', '住院', '其他'],
            'patterns': [
                (r'(?:每)?年[度]?免赔额', '年'),
                (r'每次免赔额', '次'),
                (r'每疾病免赔额', '疾病'),
                (r'每住院免赔额', '住院'),
                (r'年度累计免赔额', '年'),
            ],
            'default': '年',
        },
        
        'reimbursement_ratio_with_social_security': {
            'field_type': 'ratio',
            'unit': '%',
            'patterns': [
                (r'有基本医疗保险身份.*?(\d{1,3})%', '有医保身份'),
                (r'经基本医疗保险结算.*?(\d{1,3})%', '经医保结算'),
                (r'已参加基本医疗保险.*?(\d{1,3})%', '已参加医保'),
                (r'有社保.*?(\d{1,3})%', '有社保'),
                (r'(?:给付|赔付|报销)比例[:：]?(\d{1,3})%', '直接比例'),
            ],
            'multiplier': 0.01,  # %转小数
            'validation': {'min': 0.3, 'max': 1.0},  # 30%-100%
        },
        
        'reimbursement_ratio_without_social_security': {
            'field_type': 'ratio',
            'unit': '%',
            'patterns': [
                (r'无基本医疗保险身份.*?(\d{1,3})%', '无医保身份'),
                (r'未经基本医疗保险结算.*?(\d{1,3})%', '未经医保结算'),
                (r'未参加基本医疗保险.*?(\d{1,3})%', '未参加医保'),
                (r'无社保.*?(\d{1,3})%', '无社保'),
            ],
            'multiplier': 0.01,
            'validation': {'min': 0.3, 'max': 1.0},
        },
        
        'waiting_period_days': {
            'field_type': 'days',
            'unit': '天',
            'patterns': [
                (r'等待期[为是：:]?\s*(\d+)\s*天', '等待期'),
                (r'(\d+)\s*天.*?(?:为)?等待期', '天等待期'),
                (r'观察期[为是：:]?\s*(\d+)\s*天', '观察期'),
                (r'免责期[为是：:]?\s*(\d+)\s*天', '免责期'),
            ],
            'multiplier': 1,
            'validation': {'min': 0, 'max': 365},  # 0-365天
        },
    }
    
    def __init__(self, text: str):
        """
        初始化抽取器
        
        Args:
            text: 要分析的文本（可以是完整文档或章节文本）
        """
        self.text = text
        self.results: Dict[str, ExtractionResult] = {}
    
    def extract_all(self) -> Dict[str, ExtractionResult]:
        """
        抽取所有数值型字段
        
        Returns:
            Dict[str, ExtractionResult]: 字段名到抽取结果的映射
        """
        for field_name in self.EXTRACTION_RULES.keys():
            self.results[field_name] = self.extract_field(field_name)
        
        return self.results
    
    def extract_field(self, field_name: str) -> ExtractionResult:
        """
        抽取单个字段
        
        Args:
            field_name: 字段名称
            
        Returns:
            ExtractionResult: 抽取结果
        """
        if field_name not in self.EXTRACTION_RULES:
            return ExtractionResult(
                value=None,
                source_text=None,
                confidence=0.0,
                extractor_type="unknown"
            )
        
        rule = self.EXTRACTION_RULES[field_name]
        
        # 尝试所有模式
        for pattern, desc in rule['patterns']:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                # 安全检查：确保有捕获组
                if len(match.groups()) < 1:
                    continue
                
                # 提取原始值
                try:
                    raw_value = match.group(1).replace(',', '')
                    numeric_value = float(raw_value)
                    final_value = numeric_value * rule.get('multiplier', 1)
                    
                    # 验证
                    if self._validate_value(final_value, rule.get('validation')):
                        return ExtractionResult(
                            value=final_value,
                            source_text=match.group(0),
                            confidence=0.9,  # 直接匹配高置信度
                            extractor_type="regex_direct"
                        )
                except (ValueError, IndexError):
                    continue
        
        # 对于枚举类型，使用特殊处理
        if rule.get('field_type') == 'enum':
            return self._extract_enum_field(field_name, rule)
        
        # 未找到
        return ExtractionResult(
            value=None,
            source_text=None,
            confidence=0.0,
            extractor_type="not_found"
        )
    
    def _extract_enum_field(self, field_name: str, rule: Dict) -> ExtractionResult:
        """抽取枚举类型字段"""
        for pattern, value in rule['patterns']:
            if re.search(pattern, self.text):
                return ExtractionResult(
                    value=value,
                    source_text=f"匹配模式: {pattern}",
                    confidence=0.85,
                    extractor_type="regex_enum"
                )
        
        # 返回默认值
        default = rule.get('default')
        if default:
            return ExtractionResult(
                value=default,
                source_text=f"使用默认值: {default}",
                confidence=0.5,
                extractor_type="default"
            )
        
        return ExtractionResult(
            value=None,
            source_text=None,
            confidence=0.0,
            extractor_type="not_found"
        )
    
    def _validate_value(self, value: float, validation_rules: Optional[Dict]) -> bool:
        """验证数值是否在合理范围内"""
        if not validation_rules:
            return True
        
        min_val = validation_rules.get('min')
        max_val = validation_rules.get('max')
        
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        
        return True
    
    def extract_from_section(self, section_name: str, sections: Dict[str, str]) -> Dict[str, ExtractionResult]:
        """
        从指定章节中抽取字段
        
        Args:
            section_name: 章节名称（如"保险责任"、"续保条款"）
            sections: 章节字典（由Layer 1提供）
            
        Returns:
            Dict[str, ExtractionResult]: 抽取结果
        """
        # 查找匹配的章节
        matched_text = None
        for key, text in sections.items():
            if section_name in key or key in section_name:
                matched_text = text
                break
        
        if not matched_text:
            # 如果找不到指定章节，使用全文
            matched_text = self.text
        
        # 临时替换文本进行抽取
        original_text = self.text
        self.text = matched_text
        results = self.extract_all()
        self.text = original_text
        
        return results
    
    def get_extraction_summary(self) -> Dict[str, any]:
        """获取抽取结果摘要"""
        if not self.results:
            self.extract_all()
        
        total_fields = len(self.results)
        extracted_fields = sum(1 for r in self.results.values() if r.value is not None)
        high_confidence = sum(1 for r in self.results.values() if r.confidence >= 0.8)
        
        return {
            'total_fields': total_fields,
            'extracted_count': extracted_fields,
            'extraction_rate': extracted_fields / total_fields if total_fields > 0 else 0,
            'high_confidence_count': high_confidence,
            'average_confidence': sum(r.confidence for r in self.results.values()) / total_fields if total_fields > 0 else 0,
        }


def extract_numeric_fields(text: str, sections: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, any]]:
    """
    便捷的数值型字段抽取函数
    
    Args:
        text: 要分析的文本
        sections: 可选的章节字典，用于精准定位
        
    Returns:
        Dict: 可序列化的抽取结果
    """
    extractor = NumericFieldExtractor(text)
    results = extractor.extract_all()
    
    # 转换为可序列化的格式
    output = {}
    for field_name, result in results.items():
        output[field_name] = {
            'value': result.value,
            'source_text': result.source_text,
            'confidence': result.confidence,
            'extractor_type': result.extractor_type
        }
    
    # 添加摘要
    summary = extractor.get_extraction_summary()
    output['_summary'] = summary
    
    return output


if __name__ == "__main__":
    import sys
    import json
    
    # 测试代码
    test_text = """
    本合同年度免赔额为10000元。
    等待期为90天。
    若被保险人以有基本医疗保险身份投保且经基本医疗保险结算，赔付比例为100%。
    若未经基本医疗保险结算，赔付比例为60%。
    年度总限额为600万元。
    """
    
    if len(sys.argv) > 1 and sys.argv[1] != '--test':
        # 从文件读取
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            test_text = f.read()
    
    print("🧪 测试数值型字段抽取...")
    print("="*60)
    
    results = extract_numeric_fields(test_text)
    
    print("\n📊 抽取结果:")
    for field, data in results.items():
        if field.startswith('_'):
            continue
        print(f"\n{field}:")
        print(f"  值: {data['value']}")
        print(f"  来源: {data['source_text'][:50] if data['source_text'] else 'N/A'}...")
        print(f"  置信度: {data['confidence']:.2f}")
    
    print("\n" + "="*60)
    print(f"✅ 抽取完成！成功率: {results['_summary']['extraction_rate']:.1%}")
