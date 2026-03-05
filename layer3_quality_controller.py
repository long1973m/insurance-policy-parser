#!/usr/bin/env python3
"""
Layer 3: 冲突与质量控制技能
职责：
- 检测逻辑冲突
- 生成 extraction_quality_score
- 标记 needs_review
- 生成置信度
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json


class ConflictType(Enum):
    """冲突类型枚举"""
    LOGIC_CONTRADICTION = "logic_contradiction"  # 逻辑矛盾
    VALUE_OUT_OF_RANGE = "value_out_of_range"    # 数值超出合理范围
    MISSING_CRITICAL_FIELD = "missing_critical_field"  # 关键字段缺失
    INCONSISTENT_FORMAT = "inconsistent_format"  # 格式不一致
    SUSPICIOUS_VALUE = "suspicious_value"        # 可疑值


class Severity(Enum):
    """严重程度枚举"""
    CRITICAL = "critical"      # 严重 - 必须人工审核
    HIGH = "high"              # 高 - 建议人工审核
    MEDIUM = "medium"          # 中 - 需要注意
    LOW = "low"                # 低 - 可接受


@dataclass
class Conflict:
    """冲突/问题记录"""
    type: ConflictType
    severity: Severity
    field: Optional[str]
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    suggestion: Optional[str] = None


@dataclass
class QualityReport:
    """质量报告"""
    quality_score: float  # 0-1
    needs_review: bool
    confidence: float
    conflicts: List[Conflict]
    summary: Dict[str, Any]


class QualityController:
    """
    质量控制器
    
    功能：
    1. 检测字段间的逻辑冲突
    2. 验证数值合理性
    3. 检查关键字段完整性
    4. 计算整体质量分数
    5. 生成审核建议
    """
    
    # 关键字段列表（必须有值的字段）
    CRITICAL_FIELDS = [
        'deductible_amount',
        'reimbursement_ratio_with_social_security',
        'waiting_period_days',
    ]
    
    # 逻辑规则库
    LOGIC_RULES = [
        {
            'name': '保证续保一致性',
            'description': '如果保证续保为True，则年限应该大于0',
            'check': lambda fields: (
                fields.get('renewal_guaranteed', {}).get('value') == True and
                fields.get('renewal_guarantee_years', {}).get('value') in [None, 0]
            ),
            'severity': Severity.HIGH,
            'message': '保证续保为True但年限为0或未识别',
            'suggestion': '请核实保证续保的具体年限'
        },
        {
            'name': '赔付比例合理性',
            'description': '无社保比例不应高于有社保比例',
            'check': lambda fields: (
                fields.get('reimbursement_ratio_without_social_security', {}).get('value') and
                fields.get('reimbursement_ratio_with_social_security', {}).get('value') and
                fields['reimbursement_ratio_without_social_security']['value'] > 
                fields['reimbursement_ratio_with_social_security']['value']
            ),
            'severity': Severity.CRITICAL,
            'message': '无社保赔付比例高于有社保比例，不符合常理',
            'suggestion': '请核实赔付比例设置，通常无社保比例应低于或等于有社保比例'
        },
        {
            'name': '免赔额单位一致性',
            'description': '如果有免赔额金额，应该有单位',
            'check': lambda fields: (
                fields.get('deductible_amount', {}).get('value') is not None and
                fields.get('deductible_unit', {}).get('value') is None
            ),
            'severity': Severity.MEDIUM,
            'message': '有免赔额金额但无单位信息',
            'suggestion': '默认使用"年"作为单位，但建议核实'
        },
    ]
    
    # 数值合理性规则
    VALIDATION_RULES = {
        'total_annual_limit': {'min': 500000, 'max': 10000000, 'unit': '元'},
        'deductible_amount': {'min': 0, 'max': 50000, 'unit': '元'},
        'reimbursement_ratio_with_social_security': {'min': 0.3, 'max': 1.0, 'unit': '比例'},
        'reimbursement_ratio_without_social_security': {'min': 0.3, 'max': 1.0, 'unit': '比例'},
        'waiting_period_days': {'min': 0, 'max': 365, 'unit': '天'},
        'renewal_guarantee_years': {'min': 1, 'max': 100, 'unit': '年'},
    }
    
    def __init__(self, extraction_results: Dict[str, Dict[str, Any]]):
        """
        初始化质量控制器
        
        Args:
            extraction_results: 抽取结果字典，格式为 {field_name: {value, source_text, confidence}}
        """
        self.results = extraction_results
        self.conflicts: List[Conflict] = []
    
    def analyze(self) -> QualityReport:
        """
        执行完整的质量分析
        
        Returns:
            QualityReport: 质量报告
        """
        # 1. 检测逻辑冲突
        self._check_logic_conflicts()
        
        # 2. 验证数值合理性
        self._validate_values()
        
        # 3. 检查关键字段完整性
        self._check_critical_fields()
        
        # 4. 检测可疑值
        self._detect_suspicious_values()
        
        # 5. 计算质量分数
        quality_score = self._calculate_quality_score()
        
        # 6. 确定是否需要审核
        needs_review = any(
            c.severity in [Severity.CRITICAL, Severity.HIGH] 
            for c in self.conflicts
        )
        
        # 7. 计算整体置信度
        confidence = self._calculate_overall_confidence()
        
        # 8. 生成摘要
        summary = self._generate_summary()
        
        return QualityReport(
            quality_score=quality_score,
            needs_review=needs_review,
            confidence=confidence,
            conflicts=self.conflicts,
            summary=summary
        )
    
    def _check_logic_conflicts(self):
        """检查逻辑冲突"""
        for rule in self.LOGIC_RULES:
            try:
                if rule['check'](self.results):
                    self.conflicts.append(Conflict(
                        type=ConflictType.LOGIC_CONTRADICTION,
                        severity=rule['severity'],
                        field=None,
                        message=rule['message'],
                        suggestion=rule.get('suggestion')
                    ))
            except Exception as e:
                # 规则执行失败，记录但不中断
                self.conflicts.append(Conflict(
                    type=ConflictType.INCONSISTENT_FORMAT,
                    severity=Severity.LOW,
                    field=None,
                    message=f"规则'{rule['name']}'检查失败: {str(e)}"
                ))
    
    def _validate_values(self):
        """验证数值合理性"""
        for field_name, rule in self.VALIDATION_RULES.items():
            field_data = self.results.get(field_name, {})
            value = field_data.get('value')
            
            if value is None:
                continue
            
            min_val = rule.get('min')
            max_val = rule.get('max')
            
            if min_val is not None and value < min_val:
                self.conflicts.append(Conflict(
                    type=ConflictType.VALUE_OUT_OF_RANGE,
                    severity=Severity.HIGH,
                    field=field_name,
                    message=f"{field_name}的值{value}小于最小值{min_val}",
                    details={'value': value, 'min': min_val, 'max': max_val},
                    suggestion=f'请核实该数值是否在合理范围内'
                ))
            
            if max_val is not None and value > max_val:
                self.conflicts.append(Conflict(
                    type=ConflictType.VALUE_OUT_OF_RANGE,
                    severity=Severity.HIGH,
                    field=field_name,
                    message=f"{field_name}的值{value}大于最大值{max_val}",
                    details={'value': value, 'min': min_val, 'max': max_val},
                    suggestion=f'请核实该数值是否在合理范围内'
                ))
    
    def _check_critical_fields(self):
        """检查关键字段是否缺失"""
        for field_name in self.CRITICAL_FIELDS:
            field_data = self.results.get(field_name, {})
            value = field_data.get('value')
            
            if value is None:
                self.conflicts.append(Conflict(
                    type=ConflictType.MISSING_CRITICAL_FIELD,
                    severity=Severity.HIGH,
                    field=field_name,
                    message=f"关键字段'{field_name}'缺失",
                    suggestion='该字段对保险条款分析至关重要，建议人工补充'
                ))
    
    def _detect_suspicious_values(self):
        """检测可疑值"""
        # 检测常见的可疑模式
        suspicious_patterns = [
            {
                'field': 'waiting_period_days',
                'condition': lambda v: v == 0,
                'message': '等待期为0天，较为罕见，请核实',
                'severity': Severity.LOW
            },
            {
                'field': 'deductible_amount',
                'condition': lambda v: v == 0,
                'message': '免赔额为0，可能是高端医疗险或特殊产品',
                'severity': Severity.LOW
            },
            {
                'field': 'reimbursement_ratio_with_social_security',
                'condition': lambda v: v < 0.8,
                'message': '有社保赔付比例低于80%，低于市场平均水平',
                'severity': Severity.MEDIUM
            },
        ]
        
        for pattern in suspicious_patterns:
            field_name = pattern['field']
            field_data = self.results.get(field_name, {})
            value = field_data.get('value')
            
            if value is not None and pattern['condition'](value):
                self.conflicts.append(Conflict(
                    type=ConflictType.SUSPICIOUS_VALUE,
                    severity=pattern['severity'],
                    field=field_name,
                    message=pattern['message'],
                    details={'value': value}
                ))
    
    def _calculate_quality_score(self) -> float:
        """计算质量分数（0-1）"""
        scores = {
            'field_coverage': self._calc_field_coverage(),
            'source_text_presence': self._calc_source_presence(),
            'no_critical_conflicts': 1.0 if not any(
                c.severity == Severity.CRITICAL for c in self.conflicts
            ) else 0.0,
            'confidence_score': self._calc_average_confidence(),
        }
        
        # 加权平均
        weights = {
            'field_coverage': 0.30,
            'source_text_presence': 0.25,
            'no_critical_conflicts': 0.25,
            'confidence_score': 0.20,
        }
        
        weighted_score = sum(
            scores[key] * weights[key] for key in scores.keys()
        )
        
        return round(weighted_score, 2)
    
    def _calc_field_coverage(self) -> float:
        """计算字段覆盖率"""
        total_fields = len([k for k in self.results.keys() if not k.startswith('_')])
        extracted_fields = sum(
            1 for k, v in self.results.items() 
            if not k.startswith('_') and v.get('value') is not None
        )
        return extracted_fields / total_fields if total_fields > 0 else 0.0
    
    def _calc_source_presence(self) -> float:
        """计算source_text完整率"""
        fields_with_value = [
            v for k, v in self.results.items() 
            if not k.startswith('_') and v.get('value') is not None
        ]
        if not fields_with_value:
            return 0.0
        
        has_source = sum(1 for f in fields_with_value if f.get('source_text'))
        return has_source / len(fields_with_value)
    
    def _calc_average_confidence(self) -> float:
        """计算平均置信度"""
        confidences = [
            v.get('confidence', 0) for k, v in self.results.items() 
            if not k.startswith('_')
        ]
        return sum(confidences) / len(confidences) if confidences else 0.0
    
    def _calculate_overall_confidence(self) -> float:
        """计算整体置信度"""
        # 基于平均置信度和冲突数量
        avg_confidence = self._calc_average_confidence()
        
        # 根据冲突调整
        critical_count = sum(1 for c in self.conflicts if c.severity == Severity.CRITICAL)
        high_count = sum(1 for c in self.conflicts if c.severity == Severity.HIGH)
        
        penalty = critical_count * 0.3 + high_count * 0.15
        final_confidence = max(0.0, avg_confidence - penalty)
        
        return round(final_confidence, 2)
    
    def _generate_summary(self) -> Dict[str, Any]:
        """生成摘要统计"""
        severity_counts = {
            'critical': sum(1 for c in self.conflicts if c.severity == Severity.CRITICAL),
            'high': sum(1 for c in self.conflicts if c.severity == Severity.HIGH),
            'medium': sum(1 for c in self.conflicts if c.severity == Severity.MEDIUM),
            'low': sum(1 for c in self.conflicts if c.severity == Severity.LOW),
        }
        
        return {
            'total_conflicts': len(self.conflicts),
            'severity_distribution': severity_counts,
            'field_coverage': f"{self._calc_field_coverage():.1%}",
            'source_text_coverage': f"{self._calc_source_presence():.1%}",
            'average_confidence': f"{self._calc_average_confidence():.2f}",
        }


def quality_check(extraction_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    便捷的质量检查函数
    
    Args:
        extraction_results: 抽取结果字典
        
    Returns:
        Dict: 可序列化的质量报告
    """
    controller = QualityController(extraction_results)
    report = controller.analyze()
    
    # 转换为可序列化的字典
    return {
        'quality_score': report.quality_score,
        'needs_review': report.needs_review,
        'confidence': report.confidence,
        'conflicts': [
            {
                'type': c.type.value,
                'severity': c.severity.value,
                'field': c.field,
                'message': c.message,
                'details': c.details,
                'suggestion': c.suggestion
            }
            for c in report.conflicts
        ],
        'summary': report.summary
    }


if __name__ == "__main__":
    import sys
    
    # 测试数据
    test_results = {
        'deductible_amount': {'value': 10000, 'source_text': '免赔额10000元', 'confidence': 0.9},
        'waiting_period_days': {'value': 90, 'source_text': '等待期90天', 'confidence': 0.95},
        'reimbursement_ratio_with_social_security': {'value': 1.0, 'source_text': '100%', 'confidence': 0.9},
        'reimbursement_ratio_without_social_security': {'value': 0.6, 'source_text': '60%', 'confidence': 0.9},
        'renewal_guaranteed': {'value': True, 'source_text': '保证续保', 'confidence': 0.85},
        'renewal_guarantee_years': {'value': None, 'source_text': None, 'confidence': 0.0},  # 缺失！
    }
    
    print("🧪 测试质量控制器...")
    print("="*60)
    
    report = quality_check(test_results)
    
    print(f"\n📊 质量评分: {report['quality_score']:.2f}/1.0")
    print(f"🔍 需要审核: {'是' if report['needs_review'] else '否'}")
    print(f"🎯 整体置信度: {report['confidence']:.2f}")
    print(f"⚠️  发现问题: {len(report['conflicts'])}个")
    
    if report['conflicts']:
        print("\n📋 问题详情:")
        for i, conflict in enumerate(report['conflicts'], 1):
            print(f"\n{i}. [{conflict['severity'].upper()}] {conflict['type']}")
            print(f"   字段: {conflict['field'] or 'N/A'}")
            print(f"   描述: {conflict['message']}")
            if conflict['suggestion']:
                print(f"   建议: {conflict['suggestion']}")
    
    print("\n" + "="*60)
    print("✅ 质量检查完成！")
