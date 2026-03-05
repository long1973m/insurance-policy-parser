#!/usr/bin/env python3
"""
Layer 2 - Skill 2: 逻辑类字段抽取
职责：抽取需要逻辑判断的字段（保证续保、健康告知等）
特点：否定优先、冲突检测、覆盖机制
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class LogicPriority(Enum):
    """逻辑优先级"""
    NEGATION = 3      # 否定最高优先级
    EXPLICIT = 2      # 明确表述
    IMPLICIT = 1      # 隐含推断
    DEFAULT = 0       # 默认值


@dataclass
class LogicResult:
    """逻辑字段抽取结果"""
    value: Any
    source_text: Optional[str]
    confidence: float
    priority: LogicPriority
    reasoning: str  # 推理过程说明


class LogicFieldExtractor:
    """
    逻辑类字段抽取器
    
    核心原则：
    1. 否定优先："不保证续保" > "保证续保"
    2. 特别约定优先：特别约定章节的表述 > 一般条款
    3. 显式优于隐式：直接表述 > 间接推断
    
    抽取字段：
    - renewal_guaranteed: 是否保证续保
    - renewal_guarantee_years: 保证续保年限
    - renewal_requires_health_recheck: 续保是否需重新健康告知
    - premium_adjustment_cap: 费率调整上限
    """
    
    # 字段定义和规则
    FIELD_DEFINITIONS = {
        'renewal_guaranteed': {
            'field_type': 'boolean',
            'rules': [
                # 否定模式（最高优先级）
                {
                    'patterns': [
                        r'不保证续保',
                        r'非保证续保',
                        r'不承诺续保',
                        r'续保须经.*?(?:审核|同意|批准)',
                        r'本公司有权.*?拒绝续保',
                    ],
                    'value': False,
                    'priority': LogicPriority.NEGATION,
                    'description': '明确不保证续保'
                },
                # 肯定模式
                {
                    'patterns': [
                        r'保证续保',
                        r'承诺续保',
                        r'可保证续保',
                        r'续保权利',
                        r'保证续保权',
                    ],
                    'value': True,
                    'priority': LogicPriority.EXPLICIT,
                    'description': '明确保证续保'
                },
            ],
        },
        
        'renewal_guarantee_years': {
            'field_type': 'integer',
            'rules': [
                {
                    'patterns': [
                        (r'保证续保\s*(\d+)\s*年', 'group'),
                        (r'(\d+)\s*年保证续保', 'group'),
                        (r'每\s*(\d+)\s*年为一个保证续保期间', 'group'),
                        (r'保证续保期间[是为]?\s*(\d+)\s*年', 'group'),
                    ],
                    'extractor': 'regex_group',
                    'priority': LogicPriority.EXPLICIT,
                    'description': '明确的年数'
                },
                {
                    'patterns': [
                        r'终身保证续保',
                        r'保证续保.*终身',
                        r'续保至终身',
                    ],
                    'value': 100,  # 用100表示终身
                    'priority': LogicPriority.EXPLICIT,
                    'description': '终身续保'
                },
            ],
        },
        
        'renewal_requires_health_recheck': {
            'field_type': 'boolean',
            'rules': [
                # 不需要重新告知（对投保人更有利）
                {
                    'patterns': [
                        r'续保.*?(?:无需|不需|不用).*?(?:健康告知|告知|核保)',
                        r'(?:无需|不需|不用).*?(?:健康告知|告知|核保).*?续保',
                        r'续保.*?(?:免|免除).*?(?:健康告知|告知)',
                        r'保证续保.*?(?:不因|不因为).*?(?:健康状况|理赔记录)',
                    ],
                    'value': False,
                    'priority': LogicPriority.NEGATION,
                    'description': '明确无需重新告知'
                },
                # 需要重新告知
                {
                    'patterns': [
                        r'续保.*?(?:需要|须|应|应当).*?(?:健康告知|告知|核保)',
                        r'(?:需要|须|应|应当).*?(?:健康告知|告知|核保).*?续保',
                        r'续保时.*?重新.*?告知',
                        r'申请续保.*?(?:审核|评估)',
                    ],
                    'value': True,
                    'priority': LogicPriority.EXPLICIT,
                    'description': '明确需要重新告知'
                },
            ],
        },
        
        'premium_adjustment_cap': {
            'field_type': 'ratio',
            'rules': [
                {
                    'patterns': [
                        (r'费率调整.*?上限[是为]?\s*(\d+)%', 'group'),
                        (r'费率上调.*?不超过\s*(\d+)%', 'group'),
                        (r'价格调整.*?上限\s*(\d+)%', 'group'),
                    ],
                    'extractor': 'regex_group_ratio',
                    'multiplier': 0.01,
                    'priority': LogicPriority.EXPLICIT,
                    'description': '明确的费率上限'
                },
                {
                    'patterns': [
                        r'费率.*?(?:无限制|不限|不限制)',
                        r'本公司有权调整费率',
                    ],
                    'value': None,  # 无限制
                    'priority': LogicPriority.EXPLICIT,
                    'description': '费率无明确上限'
                },
            ],
        },
    }
    
    def __init__(self, text: str, sections: Optional[Dict[str, str]] = None):
        """
        初始化抽取器
        
        Args:
            text: 完整文本
            sections: 章节字典（用于优先级判断）
        """
        self.text = text
        self.sections = sections or {}
        self.results: Dict[str, LogicResult] = {}
        
        # 识别特别约定章节（如果有的话）
        self.special_terms_text = self._get_special_terms_section()
    
    def _get_special_terms_section(self) -> str:
        """获取特别约定章节的内容"""
        special_keywords = ['特别约定', '特别条款', '特别说明']
        for keyword in special_keywords:
            for section_name, section_text in self.sections.items():
                if keyword in section_name:
                    return section_text
        return ""
    
    def extract_all(self) -> Dict[str, LogicResult]:
        """抽取所有逻辑类字段"""
        for field_name in self.FIELD_DEFINITIONS.keys():
            self.results[field_name] = self.extract_field(field_name)
        return self.results
    
    def extract_field(self, field_name: str) -> LogicResult:
        """
        抽取单个逻辑字段
        
        策略：
        1. 先在特别约定中查找（优先级更高）
        2. 然后在全文查找
        3. 应用否定优先原则
        """
        if field_name not in self.FIELD_DEFINITIONS:
            return LogicResult(
                value=None,
                source_text=None,
                confidence=0.0,
                priority=LogicPriority.DEFAULT,
                reasoning="未知字段"
            )
        
        definition = self.FIELD_DEFINITIONS[field_name]
        
        # 收集所有匹配结果
        matches = []
        
        # 1. 在特别约定中查找（权重更高）
        if self.special_terms_text:
            for rule in definition['rules']:
                match = self._apply_rule(rule, self.special_terms_text)
                if match:
                    matches.append((*match, 'special_terms'))
        
        # 2. 在全文中查找
        for rule in definition['rules']:
            match = self._apply_rule(rule, self.text)
            if match:
                matches.append((*match, 'full_text'))
        
        if not matches:
            return LogicResult(
                value=None,
                source_text=None,
                confidence=0.0,
                priority=LogicPriority.DEFAULT,
                reasoning="未找到匹配"
            )
        
        # 按优先级排序（高优先级在前）
        matches.sort(key=lambda x: x[2].value, reverse=True)
        
        # 选择最高优先级的结果
        best_match = matches[0]
        value, source_text, priority, reasoning, source_type = best_match
        
        # 计算置信度
        confidence = self._calculate_confidence(priority, source_type, len(matches))
        
        return LogicResult(
            value=value,
            source_text=source_text,
            confidence=confidence,
            priority=priority,
            reasoning=f"{reasoning} (来源: {source_type})"
        )
    
    def _apply_rule(self, rule: Dict, text: str) -> Optional[Tuple[Any, str, LogicPriority, str]]:
        """应用单条规则"""
        patterns = rule.get('patterns', [])
        extractor_type = rule.get('extractor', 'direct')
        
        for pattern in patterns:
            if isinstance(pattern, tuple):
                # 带提取组的模式
                regex_pattern, extract_method = pattern
                match = re.search(regex_pattern, text, re.IGNORECASE)
                if match:
                    if extract_method == 'group':
                        try:
                            value = int(match.group(1))
                            multiplier = rule.get('multiplier', 1)
                            final_value = value * multiplier
                            return (
                                final_value,
                                match.group(0),
                                rule['priority'],
                                rule['description']
                            )
                        except (ValueError, IndexError):
                            continue
                    elif extract_method == 'regex_group_ratio':
                        try:
                            value = int(match.group(1))
                            multiplier = rule.get('multiplier', 0.01)
                            final_value = value * multiplier
                            return (
                                final_value,
                                match.group(0),
                                rule['priority'],
                                rule['description']
                            )
                        except (ValueError, IndexError):
                            continue
            else:
                # 直接匹配模式
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return (
                        rule['value'],
                        match.group(0),
                        rule['priority'],
                        rule['description']
                    )
        
        return None
    
    def _calculate_confidence(self, priority: LogicPriority, source_type: str, match_count: int) -> float:
        """计算置信度"""
        base_confidence = {
            LogicPriority.NEGATION: 0.95,
            LogicPriority.EXPLICIT: 0.85,
            LogicPriority.IMPLICIT: 0.60,
            LogicPriority.DEFAULT: 0.30,
        }.get(priority, 0.50)
        
        # 特别约定加分
        if source_type == 'special_terms':
            base_confidence += 0.05
        
        # 多个匹配减分（可能有冲突）
        if match_count > 2:
            base_confidence -= 0.10
        
        return min(1.0, max(0.0, base_confidence))
    
    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """
        检测字段间的逻辑冲突
        
        Returns:
            冲突列表
        """
        conflicts = []
        
        # 检查保证续保一致性
        renewal = self.results.get('renewal_guaranteed')
        years = self.results.get('renewal_guarantee_years')
        
        if renewal and years:
            if renewal.value == True and years.value in [None, 0]:
                conflicts.append({
                    'type': 'logic_conflict',
                    'fields': ['renewal_guaranteed', 'renewal_guarantee_years'],
                    'message': '保证续保为True但年限为0或未识别',
                    'severity': 'high'
                })
        
        # 检查是否有矛盾的表述
        for field_name, result in self.results.items():
            if result.priority == LogicPriority.NEGATION:
                # 检查是否有同字段的肯定表述
                # 这里简化处理，实际可以保存所有匹配
                pass
        
        return conflicts


def extract_logic_fields(text: str, sections: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, Any]]:
    """
    便捷的逻辑类字段抽取函数
    
    Args:
        text: 要分析的文本
        sections: 可选的章节字典
        
    Returns:
        Dict: 可序列化的抽取结果
    """
    extractor = LogicFieldExtractor(text, sections)
    results = extractor.extract_all()
    conflicts = extractor.detect_conflicts()
    
    # 转换为可序列化的格式
    output = {}
    for field_name, result in results.items():
        output[field_name] = {
            'value': result.value,
            'source_text': result.source_text,
            'confidence': result.confidence,
            'priority': result.priority.name,
            'reasoning': result.reasoning
        }
    
    output['_conflicts'] = conflicts
    output['_summary'] = {
        'total_fields': len(results),
        'extracted_count': sum(1 for r in results.values() if r.value is not None),
        'high_confidence_count': sum(1 for r in results.values() if r.confidence >= 0.8),
        'conflict_count': len(conflicts)
    }
    
    return output


if __name__ == "__main__":
    import sys
    import json
    
    # 测试数据
    test_text = """
    本合同保证续保，每5年为一个保证续保期间。
    续保无需重新进行健康告知。
    费率调整上限为30%。
    """
    
    print("🧪 测试逻辑类字段抽取...")
    print("="*60)
    
    results = extract_logic_fields(test_text)
    
    print("\n📊 抽取结果:")
    for field, data in results.items():
        if field.startswith('_'):
            continue
        print(f"\n{field}:")
        print(f"  值: {data['value']}")
        print(f"  置信度: {data['confidence']:.2f}")
        print(f"  优先级: {data['priority']}")
        print(f"  推理: {data['reasoning']}")
    
    if results['_conflicts']:
        print("\n⚠️  检测到冲突:")
        for conflict in results['_conflicts']:
            print(f"  - {conflict['message']}")
    
    print("\n" + "="*60)
    print(f"✅ 完成！成功率: {results['_summary']['extracted_count']}/{results['_summary']['total_fields']}")
