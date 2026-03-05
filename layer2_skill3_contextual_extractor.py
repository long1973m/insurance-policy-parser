#!/usr/bin/env python3
"""
Layer 2 - Skill 3: 场景限制类字段抽取
职责：抽取需要语境理解的字段（医院要求、特殊限制等）
特点：语境识别、主体角色判断、多条件组合
"""

import re
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
from enum import Enum


class ContextType(Enum):
    """语境类型"""
    GENERAL = "general"           # 一般情况
    EMERGENCY = "emergency"       # 紧急情况
    SPECIFIC_DISEASE = "disease"  # 特定疾病
    SPECIAL_TREATMENT = "treatment"  # 特殊治疗


@dataclass
class ContextualResult:
    """场景类字段抽取结果"""
    value: Any
    source_text: Optional[str]
    confidence: float
    context: ContextType  # 适用语境
    conditions: List[str]  # 附加条件


class ContextualFieldExtractor:
    """
    场景限制类字段抽取器
    
    核心能力：
    1. 语境识别：区分一般情况 vs 紧急情况
    2. 主体角色：被保险人的行为限制
    3. 多条件组合：医院等级 + 医院性质 + 地域限制
    
    抽取字段：
    - hospital_level_requirement: 医院等级要求
    - public_hospital_required: 是否仅限公立医院
    - emergency_hospital_exception: 紧急情况医院例外
    - overseas_treatment_covered: 海外就医
    - green_channel_covered: 绿色通道
    - claim_direct_billing_available: 直付服务
    """
    
    # 医院等级关键词映射
    HOSPITAL_LEVEL_KEYWORDS = {
        '三级及以上': ['三级', '三甲', '三级甲等', '三级以上'],
        '二级及以上': ['二级', '二甲', '二级甲等', '二级以上', '县市级'],
        '一级及以上': ['一级', '一甲', '一级以上', '乡镇级'],
        '无限制': ['不限等级', '各级医院', '所有医院', '无等级限制'],
    }
    
    # 医院性质关键词
    HOSPITAL_TYPE_KEYWORDS = {
        'public': ['公立', '医保定点', '社保定点', '定点医院'],
        'private': ['私立', '民营', '私营'],
    }
    
    # 语境标记词
    CONTEXT_MARKERS = {
        ContextType.EMERGENCY: ['紧急', '急救', '急诊', '抢救', '危及生命'],
        ContextType.SPECIFIC_DISEASE: ['恶性肿瘤', '重疾', '重大疾病', '特定疾病'],
        ContextType.SPECIAL_TREATMENT: ['质子重离子', '靶向治疗', 'CAR-T', '器官移植'],
    }
    
    def __init__(self, text: str, sections: Optional[Dict[str, str]] = None):
        self.text = text
        self.sections = sections or {}
        self.results: Dict[str, ContextualResult] = {}
        
        # 提取医疗机构相关章节
        self.hospital_section = self._get_hospital_section()
        
    def _get_hospital_section(self) -> str:
        """获取医疗机构相关章节的内容"""
        hospital_keywords = ['医院', '医疗机构', '就诊', '治疗']
        
        for section_name, section_text in self.sections.items():
            for keyword in hospital_keywords:
                if keyword in section_name:
                    return section_text
        
        # 如果没找到，返回全文
        return self.text
    
    def extract_all(self) -> Dict[str, ContextualResult]:
        """抽取所有场景类字段"""
        self._extract_hospital_requirements()
        self._extract_overseas_treatment()
        self._extract_value_added_services()
        self._extract_emergency_exceptions()
        
        return self.results
    
    def _extract_hospital_requirements(self):
        """抽取医院要求"""
        # 医院等级
        level_found = False
        for level_name, keywords in self.HOSPITAL_LEVEL_KEYWORDS.items():
            for keyword in keywords:
                # 查找医院等级表述
                patterns = [
                    rf'{keyword}.*?医院',
                    rf'医院.*?{keyword}',
                    rf'在{keyword}',
                    rf'{keyword}(?:及)?以上',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, self.hospital_section)
                    if match:
                        # 检查是否有否定
                        context_start = max(0, match.start() - 50)
                        context = self.hospital_section[context_start:match.end()]
                        
                        if not self._has_negation(context):
                            self.results['hospital_level_requirement'] = ContextualResult(
                                value=level_name,
                                source_text=match.group(0),
                                confidence=0.85,
                                context=ContextType.GENERAL,
                                conditions=[]
                            )
                            level_found = True
                            break
                
                if level_found:
                    break
            if level_found:
                break
        
        if not level_found:
            self.results['hospital_level_requirement'] = ContextualResult(
                value=None,
                source_text=None,
                confidence=0.0,
                context=ContextType.GENERAL,
                conditions=[]
            )
        
        # 是否仅限公立
        public_found = False
        
        # 检查明确提及公立
        public_patterns = [
            r'公立(?:医院)?',
            r'医保定点(?:医院)?',
            r'定点医院',
        ]
        
        for pattern in public_patterns:
            matches = list(re.finditer(pattern, self.hospital_section))
            if matches:
                # 检查是否有私立选项
                has_private_option = bool(re.search(r'私立|民营.*?(?:可|可以)', self.hospital_section))
                
                value = True if not has_private_option else False
                
                self.results['public_hospital_required'] = ContextualResult(
                    value=value,
                    source_text=matches[0].group(0),
                    confidence=0.80 if not has_private_option else 0.60,
                    context=ContextType.GENERAL,
                    conditions=['仅限公立' if not has_private_option else '私立也可']
                )
                public_found = True
                break
        
        if not public_found:
            self.results['public_hospital_required'] = ContextualResult(
                value=None,
                source_text=None,
                confidence=0.0,
                context=ContextType.GENERAL,
                conditions=[]
            )
    
    def _extract_overseas_treatment(self):
        """抽取海外就医"""
        overseas_patterns = [
            r'海外(?:就医|治疗)',
            r'境外(?:医疗|治疗)',
            r'国外(?:就医|治疗)',
            r'港澳台(?:地区)?',
        ]
        
        for pattern in overseas_patterns:
            match = re.search(pattern, self.text)
            if match:
                # 检查是否包含
                context_start = max(0, match.start() - 100)
                context_end = min(len(self.text), match.end() + 100)
                context = self.text[context_start:context_end]
                
                # 判断是否包含保障
                if not self._has_negation(context):
                    self.results['overseas_treatment_covered'] = ContextualResult(
                        value=True,
                        source_text=match.group(0),
                        confidence=0.75,
                        context=ContextType.GENERAL,
                        conditions=[]
                    )
                    return
        
        self.results['overseas_treatment_covered'] = ContextualResult(
            value=False,  # 默认不包含
            source_text=None,
            confidence=0.50,
            context=ContextType.GENERAL,
            conditions=['默认不包含']
        )
    
    def _extract_value_added_services(self):
        """抽取增值服务"""
        # 绿色通道
        green_channel_patterns = [
            r'绿色通道',
            r'就医绿通',
            r'专家预约',
            r'优先就诊',
        ]
        
        green_found = False
        for pattern in green_channel_patterns:
            match = re.search(pattern, self.text)
            if match:
                self.results['green_channel_covered'] = ContextualResult(
                    value=True,
                    source_text=match.group(0),
                    confidence=0.70,
                    context=ContextType.GENERAL,
                    conditions=[]
                )
                green_found = True
                break
        
        if not green_found:
            self.results['green_channel_covered'] = ContextualResult(
                value=None,
                source_text=None,
                confidence=0.0,
                context=ContextType.GENERAL,
                conditions=[]
            )
        
        # 直付服务
        direct_billing_patterns = [
            r'直付',
            r'直接结算',
            r'医疗直付',
            r'垫付',
        ]
        
        billing_found = False
        for pattern in direct_billing_patterns:
            match = re.search(pattern, self.text)
            if match:
                # 排除"不直付"等否定情况
                context_start = max(0, match.start() - 30)
                context = self.text[context_start:match.end()]
                
                if not self._has_negation(context):
                    self.results['claim_direct_billing_available'] = ContextualResult(
                        value=True,
                        source_text=match.group(0),
                        confidence=0.75,
                        context=ContextType.GENERAL,
                        conditions=[]
                    )
                    billing_found = True
                    break
        
        if not billing_found:
            self.results['claim_direct_billing_available'] = ContextualResult(
                value=None,
                source_text=None,
                confidence=0.0,
                context=ContextType.GENERAL,
                conditions=[]
            )
    
    def _extract_emergency_exceptions(self):
        """抽取紧急情况例外"""
        # 查找紧急情况的特殊规定
        emergency_patterns = [
            r'紧急.*?(?:不受|突破).*?等级',
            r'急救.*?(?:不限|任何医院)',
            r'急诊.*?(?:可|可以).*?(?:就近|任何)',
            r'危及生命.*?(?:不受限|可突破)',
        ]
        
        for pattern in emergency_patterns:
            match = re.search(pattern, self.text)
            if match:
                self.results['emergency_hospital_exception'] = ContextualResult(
                    value=True,
                    source_text=match.group(0),
                    confidence=0.80,
                    context=ContextType.EMERGENCY,
                    conditions=['紧急情况']
                )
                return
        
        # 如果没有找到明确的例外条款，检查是否有紧急情况的一般描述
        emergency_general = re.search(r'紧急医疗|急救处理', self.text)
        if emergency_general:
            self.results['emergency_hospital_exception'] = ContextualResult(
                value=None,  # 不确定
                source_text=emergency_general.group(0),
                confidence=0.40,
                context=ContextType.EMERGENCY,
                conditions=['需人工确认']
            )
        else:
            self.results['emergency_hospital_exception'] = ContextualResult(
                value=None,
                source_text=None,
                confidence=0.0,
                context=ContextType.EMERGENCY,
                conditions=[]
            )
    
    def _has_negation(self, text: str) -> bool:
        """检查文本中是否有否定词"""
        negation_patterns = [
            r'不[^\s]{0,5}?(?:包括|含|覆盖|承担)',
            r'(?:不含|不包括|不承担|不覆盖)',
            r'除外',
            r'免责',
        ]
        
        for pattern in negation_patterns:
            if re.search(pattern, text):
                return True
        
        return False
    
    def analyze_context(self, field_name: str) -> Dict[str, Any]:
        """
        分析特定字段的语境信息
        
        Args:
            field_name: 字段名称
            
        Returns:
            语境分析结果
        """
        result = self.results.get(field_name)
        if not result:
            return {'error': '字段未抽取'}
        
        return {
            'value': result.value,
            'applicable_context': result.context.value,
            'conditions': result.conditions,
            'confidence': result.confidence,
            'recommendations': self._generate_recommendations(field_name, result)
        }
    
    def _generate_recommendations(self, field_name: str, result: ContextualResult) -> List[str]:
        """生成审核建议"""
        recommendations = []
        
        if result.confidence < 0.5:
            recommendations.append(f"{field_name}置信度较低，建议人工核实")
        
        if result.context == ContextType.EMERGENCY and result.value is None:
            recommendations.append("紧急情况条款不明确，建议确认是否有医院等级例外")
        
        if result.conditions:
            recommendations.append(f"该字段有条件限制: {', '.join(result.conditions)}")
        
        return recommendations


def extract_contextual_fields(text: str, sections: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, Any]]:
    """
    便捷的场景类字段抽取函数
    
    Args:
        text: 要分析的文本
        sections: 可选的章节字典
        
    Returns:
        Dict: 可序列化的抽取结果
    """
    extractor = ContextualFieldExtractor(text, sections)
    results = extractor.extract_all()
    
    # 转换为可序列化的格式
    output = {}
    for field_name, result in results.items():
        output[field_name] = {
            'value': result.value,
            'source_text': result.source_text,
            'confidence': result.confidence,
            'context': result.context.value,
            'conditions': result.conditions
        }
    
    output['_summary'] = {
        'total_fields': len(results),
        'extracted_count': sum(1 for r in results.values() if r.value is not None),
        'with_conditions': sum(1 for r in results.values() if r.conditions),
    }
    
    return output


if __name__ == "__main__":
    import json
    
    # 测试数据
    test_text = """
    被保险人应在中华人民共和国境内二级及以上公立医院普通部就诊。
    紧急情况不受医院等级限制。
    包含海外就医保障。
    提供就医绿色通道服务。
    支持医疗费用直付。
    """
    
    print("🧪 测试场景类字段抽取...")
    print("="*60)
    
    results = extract_contextual_fields(test_text)
    
    print("\n📊 抽取结果:")
    for field, data in results.items():
        if field.startswith('_'):
            continue
        print(f"\n{field}:")
        print(f"  值: {data['value']}")
        print(f"  语境: {data['context']}")
        print(f"  条件: {data['conditions']}")
        print(f"  置信度: {data['confidence']:.2f}")
    
    print("\n" + "="*60)
    print(f"✅ 完成！成功率: {results['_summary']['extracted_count']}/{results['_summary']['total_fields']}")
