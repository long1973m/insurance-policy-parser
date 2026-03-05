#!/usr/bin/env python3
"""
保险条款核心字段抽取工具 V2
基于标准化字段表格，从PDF保险条款中抽取结构化数据
支持 Level 1（绝对核心）和 Level 2（对比增强）字段
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

try:
    from PyPDF2 import PdfReader
except ImportError:
    raise ImportError("请先安装 PyPDF2: pip install PyPDF2")


@dataclass
class InsurancePolicyFields:
    """保险条款核心字段数据结构"""
    
    # ========== Level 1: 绝对核心字段（16个）==========
    # 基础参数
    total_annual_limit: Optional[float] = None          # 年度总赔付限额
    deductible_amount: Optional[float] = None           # 免赔额金额
    deductible_unit: Optional[str] = None               # 免赔额单位：年/次/疾病/住院/其他
    
    # 赔付比例
    reimbursement_ratio_with_social_security: Optional[float] = None    # 有社保赔付比例
    reimbursement_ratio_without_social_security: Optional[float] = None # 无社保赔付比例
    
    # 续保条款
    renewal_guaranteed: Optional[bool] = None           # 是否保证续保
    renewal_requires_health_recheck: Optional[bool] = None  # 续保是否需重新健康告知
    renewal_guarantee_years: Optional[int] = None       # 保证续保年限
    premium_adjustment_cap: Optional[float] = None      # 费率上调上限
    
    # 医院要求
    hospital_level_requirement: Optional[str] = None    # 医院等级要求
    public_hospital_required: Optional[bool] = None     # 是否仅限公立医院
    
    # 等待期与基础责任
    waiting_period_days: Optional[int] = None           # 等待期天数
    inpatient_medical_covered: Optional[bool] = None    # 是否保障住院医疗
    drug_coverage_scope: Optional[str] = None           # 药品保障范围
    out_of_hospital_drug_covered: Optional[bool] = None # 是否保障院外购药
    proton_heavy_ion_covered: Optional[bool] = None     # 是否涵盖质子重离子
    
    # ========== Level 2: 对比增强字段（16个）==========
    deductible_family_shared: Optional[bool] = None         # 家庭共享免赔额
    social_security_offset_allowed: Optional[bool] = None   # 医保可抵扣免赔额
    special_outpatient_covered: Optional[bool] = None       # 特殊门诊
    outpatient_surgery_covered: Optional[bool] = None       # 门诊手术
    pre_post_hospital_outpatient_days: Optional[int] = None # 住院前后门急诊天数
    critical_disease_deductible_zero: Optional[bool] = None # 重疾0免赔
    critical_disease_separate_limit: Optional[bool] = None  # 重疾独立保额
    targeted_drug_covered: Optional[bool] = None            # 靶向药
    car_t_covered: Optional[bool] = None                    # CAR-T治疗
    designated_drug_list_required: Optional[bool] = None    # 是否需指定药品清单
    emergency_hospital_exception: Optional[bool] = None     # 紧急情况医院等级例外
    overseas_treatment_covered: Optional[bool] = None       # 海外就医
    post_stop_transfer_right: Optional[bool] = None         # 停售转保权
    green_channel_covered: Optional[bool] = None            # 绿色通道
    claim_direct_billing_available: Optional[bool] = None   # 直付服务
    family_plan_available: Optional[bool] = None            # 家庭单投保
    
    # 元数据
    product_name: Optional[str] = None                  # 产品名称
    insurance_company: Optional[str] = None             # 保险公司


class InsurancePolicyExtractor:
    """保险条款字段抽取器"""
    
    def __init__(self, text: str):
        self.text = text
        self.fields = InsurancePolicyFields()
    
    def extract_all(self) -> InsurancePolicyFields:
        """抽取所有字段"""
        self._extract_level1_fields()
        self._extract_level2_fields()
        return self.fields
    
    # ========== Level 1 字段抽取方法 ==========
    
    def _extract_level1_fields(self):
        """抽取 Level 1 绝对核心字段"""
        self._extract_product_info()
        self._extract_annual_limit()
        self._extract_deductible()
        self._extract_reimbursement_ratios()
        self._extract_renewal_terms()
        self._extract_hospital_requirements()
        self._extract_waiting_period()
        self._extract_basic_coverage()
        self._extract_advanced_treatments()
    
    def _extract_product_info(self):
        """抽取产品基本信息"""
        # 产品名称
        name_patterns = [
            r'(\S+?医疗保险.*?条款)',
            r'(\S+?重疾险.*?条款)',
            r'(\S+?意外险.*?条款)',
            r'([\u4e00-\u9fa5]+保险[^\n]{0,20}条款)'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, self.text)
            if match:
                self.fields.product_name = match.group(1).strip()
                break
        
        # 保险公司
        company_patterns = [
            r'([\u4e00-\u9fa5]+人寿保险有限公司)',
            r'([\u4e00-\u9fa5]+财产保险股份有限公司)',
            r'([\u4e00-\u9fa5]+养老保险股份有限公司)',
            r'承保.*?([\u4e00-\u9fa5]{2,10}保险)',
        ]
        for pattern in company_patterns:
            match = re.search(pattern, self.text)
            if match:
                self.fields.insurance_company = match.group(1).strip()
                break
    
    def _extract_annual_limit(self):
        """抽取年度总赔付限额"""
        # 首先尝试直接匹配年度限额表述
        patterns = [
            r'年度.*?(?:限额|保额|赔付上限).*?(\d{1,3}(?:,\d{3})*)\s*万',
            r'最高.*?(?:赔付|给付|累计).*?(\d{1,3}(?:,\d{3})*)\s*万',
            r'年度累计.*?([\d,]+)\s*万元',
        ]
        for pattern in patterns:
            match = re.search(pattern, self.text)
            if match:
                amount_str = match.group(1).replace(',', '')
                self.fields.total_annual_limit = float(amount_str) * 10000
                return
        
        # 如果没有找到，尝试从保险责任部分查找常见保额数字
        # 百万医疗险通常是200万、300万、400万、600万等
        coverage_section = re.search(r'保险责任[\s\S]{0,2000}', self.text)
        if coverage_section:
            section_text = coverage_section.group()
            # 查找常见的保额数字（200万-800万之间）
            amount_matches = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*万', section_text)
            valid_amounts = []
            for amt_str in amount_matches:
                amt = int(amt_str.replace(',', ''))
                if 100 <= amt <= 1000:  # 百万医疗险常见范围
                    valid_amounts.append(amt)
            if valid_amounts:
                # 取最大的作为年度总限额
                self.fields.total_annual_limit = max(valid_amounts) * 10000
    
    def _extract_deductible(self):
        """抽取免赔额信息"""
        # 免赔额金额
        patterns = [
            r'免赔额[为：:]?(\d{1,3}(?:,\d{3})*)\s*元',
            r'免赔额.*?([\d,]+)\s*元',
            r'([\d,]+)\s*元.*?(?:年)?度免赔额',
        ]
        for pattern in patterns:
            match = re.search(pattern, self.text)
            if match:
                amount_str = match.group(1).replace(',', '')
                self.fields.deductible_amount = float(amount_str)
                break
        
        # 免赔额单位
        unit_patterns = [
            (r'(?:每)?年[度]?免赔额', '年'),
            (r'每次免赔额', '次'),
            (r'每疾病免赔额', '疾病'),
            (r'每住院免赔额', '住院'),
        ]
        for pattern, unit in unit_patterns:
            if re.search(pattern, self.text):
                self.fields.deductible_unit = unit
                break
        if not self.fields.deductible_unit and self.fields.deductible_amount:
            self.fields.deductible_unit = '年'  # 默认年度
    
    def _extract_reimbursement_ratios(self):
        """抽取赔付比例"""
        # 查找所有百分比（排除明显不是赔付比例的数字如年份、天数等）
        all_percentages = re.findall(r'(\d{1,3})%', self.text)
        # 过滤：赔付比例通常在30%-100%之间
        valid_percentages = [int(p) for p in all_percentages if 30 <= int(p) <= 100]
        
        # 有社保/无社保比例 - 在相关段落中查找
        ss_patterns = [
            r'(?:以有社保身份|有社保|经社保|已参加社保)[\s\S]{0,300}?(\d{1,3})%',
            r'(?:给付比例|赔付比例)[^。]*?(?:社保|医保)[^。]*?(\d{1,3})%',
        ]
        no_ss_patterns = [
            r'(?:未以有社保|无社保|未经社保|未参加社保)[\s\S]{0,300}?(\d{1,3})%',
            r'(?:给付比例|赔付比例)[^。]*?(?:未经|无|未参加)[^。]*?(\d{1,3})%',
        ]
        
        for pattern in ss_patterns:
            match = re.search(pattern, self.text)
            if match:
                pct = int(match.group(1))
                if 30 <= pct <= 100:
                    self.fields.reimbursement_ratio_with_social_security = pct / 100
                    break
        
        for pattern in no_ss_patterns:
            match = re.search(pattern, self.text)
            if match:
                pct = int(match.group(1))
                if 30 <= pct <= 100:
                    self.fields.reimbursement_ratio_without_social_security = pct / 100
                    break
        
        # 如果还是没找到，使用合理的推断逻辑
        if not self.fields.reimbursement_ratio_with_social_security and valid_percentages:
            # 有社保通常是100%或最高的比例
            self.fields.reimbursement_ratio_with_social_security = max(valid_percentages) / 100
        
        if not self.fields.reimbursement_ratio_without_social_security and valid_percentages:
            # 无社保通常是60%或较低的比例（但不是最低的小比例）
            sorted_pct = sorted(valid_percentages, reverse=True)
            if len(sorted_pct) >= 2:
                # 取第二高的作为无社保比例（通常是60%）
                self.fields.reimbursement_ratio_without_social_security = sorted_pct[1] / 100
            else:
                # 如果只有一个比例，无社保默认60%
                self.fields.reimbursement_ratio_without_social_security = 0.6
    
    def _extract_renewal_terms(self):
        """抽取续保条款"""
        # 保证续保
        if re.search(r'保证续保|承诺续保|可保证续保', self.text):
            self.fields.renewal_guaranteed = True
        elif re.search(r'不保证续保|非保证续保', self.text):
            self.fields.renewal_guaranteed = False
        
        # 保证续保年限
        year_patterns = [
            r'保证续保\s*(\d+)\s*年',
            r'(\d+)\s*年保证续保',
            r'保证续保期间[为：:]?(\d+)\s*年',
            r'每\s*(\d+)\s*年为一个保证续保期间',
            r'保证续保期间.*?每\s*(\d+)\s*年',
        ]
        for pattern in year_patterns:
            match = re.search(pattern, self.text)
            if match:
                years = int(match.group(1))
                self.fields.renewal_guarantee_years = years
                self.fields.renewal_guaranteed = True
                break
        
        # 终身续保
        if re.search(r'终身保证续保|保证续保.*终身', self.text):
            self.fields.renewal_guarantee_years = 100
            self.fields.renewal_guaranteed = True
        
        # 续保是否需重新健康告知
        if re.search(r'续保.*?(?:无需|不需|不用).*?(?:健康告知|告知)', self.text):
            self.fields.renewal_requires_health_recheck = False
        elif re.search(r'续保.*?(?:需要|须|应).*?(?:健康告知|告知|核保)', self.text):
            self.fields.renewal_requires_health_recheck = True
        
        # 费率调整上限
        cap_match = re.search(r'费率调整.*?上限[为：:]?(\d+)%', self.text)
        if cap_match:
            self.fields.premium_adjustment_cap = int(cap_match.group(1)) / 100
    
    def _extract_hospital_requirements(self):
        """抽取医院要求"""
        # 医院等级
        if re.search(r'三级(?:及)?以上|三甲', self.text):
            self.fields.hospital_level_requirement = '三级及以上'
        elif re.search(r'二级(?:及)?以上', self.text):
            self.fields.hospital_level_requirement = '二级及以上'
        elif re.search(r'一级(?:及)?以上', self.text):
            self.fields.hospital_level_requirement = '一级及以上'
        elif re.search(r'不限等级|无等级限制|各级医院', self.text):
            self.fields.hospital_level_requirement = '无限制'
        
        # 是否仅限公立
        if re.search(r'公立|医保定点', self.text) and not re.search(r'私立|民营', self.text):
            self.fields.public_hospital_required = True
        elif re.search(r'私立|民营.*?(?:可赔|包含|涵盖)', self.text):
            self.fields.public_hospital_required = False
    
    def _extract_waiting_period(self):
        """抽取等待期"""
        patterns = [
            r'等待期[为：:]?(\d+)\s*天',
            r'(\d+)\s*天.*?(?:为)?等待期',
            r'观察期[为：:]?(\d+)\s*天',
        ]
        for pattern in patterns:
            match = re.search(pattern, self.text)
            if match:
                self.fields.waiting_period_days = int(match.group(1))
                break
    
    def _extract_basic_coverage(self):
        """抽取基础保障责任"""
        # 住院医疗
        if re.search(r'一般住院医疗|住院医疗保险金|住院医疗费用', self.text):
            self.fields.inpatient_medical_covered = True
        
        # 药品保障范围
        if re.search(r'社保目录内|医保目录内|国家医保', self.text):
            self.fields.drug_coverage_scope = '社保目录内'
        elif re.search(r'药品清单|特定药品清单', self.text):
            self.fields.drug_coverage_scope = '药品保障清单内'
        elif re.search(r'全部药品|所有药品|合理且必要', self.text):
            self.fields.drug_coverage_scope = '全部'
        else:
            self.fields.drug_coverage_scope = '未明确'
        
        # 院外购药
        if re.search(r'院外特定药品|外购药|院外购药|DTP药房', self.text):
            self.fields.out_of_hospital_drug_covered = True
        elif re.search(r'不含院外|院外.*?(?:不赔|除外)', self.text):
            self.fields.out_of_hospital_drug_covered = False
    
    def _extract_advanced_treatments(self):
        """抽取高端治疗项目"""
        # 质子重离子
        if re.search(r'质子重离子|质子、重离子|质子治疗', self.text):
            self.fields.proton_heavy_ion_covered = True
        elif re.search(r'不含质子|质子.*?(?:不赔|除外)', self.text):
            self.fields.proton_heavy_ion_covered = False
    
    # ========== Level 2 字段抽取方法 ==========
    
    def _extract_level2_fields(self):
        """抽取 Level 2 对比增强字段"""
        self._extract_family_features()
        self._extract_outpatient_features()
        self._extract_critical_disease_features()
        self._extract_drug_features()
        self._extract_special_services()
        self._extract_emergency_overseas()
    
    def _extract_family_features(self):
        """抽取家庭相关特性"""
        # 家庭共享免赔额
        if re.search(r'家庭共享免赔额|全家共享|家庭单.*免赔额', self.text):
            self.fields.deductible_family_shared = True
        
        # 医保抵扣免赔额
        if re.search(r'医保报销.*抵扣免赔额|社保.*抵扣|医保.*计入免赔额', self.text):
            self.fields.social_security_offset_allowed = True
        
        # 家庭单投保
        if re.search(r'家庭单|家庭成员.*投保|家属.*投保', self.text):
            self.fields.family_plan_available = True
    
    def _extract_outpatient_features(self):
        """抽取门诊相关特性"""
        # 特殊门诊
        if re.search(r'特殊门诊|门诊肾透析|门诊放化疗|器官移植后抗排异', self.text):
            self.fields.special_outpatient_covered = True
        
        # 门诊手术
        if re.search(r'门诊手术|日间手术', self.text):
            self.fields.outpatient_surgery_covered = True
        
        # 住院前后门急诊天数
        patterns = [
            (r'住院前\s*(\d+)\s*日?及?.*?出院后\s*(\d+)\s*日', 'sum'),  # 住院前30日及出院后30日
            (r'住院前\s*(\d+)\s*天.*住院后\s*(\d+)\s*天', 'sum'),
            (r'住院前后各\s*(\d+)\s*天', 'each'),  # 住院前后各30天 = 60天
            (r'住院前后门急诊.*?(\d+)\s*天', 'total'),  # 直接说XX天
        ]
        for pattern, calc_type in patterns:
            match = re.search(pattern, self.text)
            if match:
                if calc_type == 'sum':
                    # 住院前X天 + 出院后X天
                    days = int(match.group(1)) + int(match.group(2))
                elif calc_type == 'each':
                    # 前后各X天 = X * 2
                    days = int(match.group(1)) * 2
                else:
                    # 直接总数
                    days = int(match.group(1))
                self.fields.pre_post_hospital_outpatient_days = days
                break
    
    def _extract_critical_disease_features(self):
        """抽取重疾相关特性"""
        # 重疾0免赔
        if re.search(r'重疾.*0免赔|重大疾病.*零免赔|重疾.*无免赔', self.text):
            self.fields.critical_disease_deductible_zero = True
        
        # 重疾独立保额
        if re.search(r'重疾.*单独限额|重大疾病.*独立保额|重疾.*不占用', self.text):
            self.fields.critical_disease_separate_limit = True
    
    def _extract_drug_features(self):
        """抽取药品相关特性"""
        # 靶向药
        if re.search(r'靶向药|靶向治疗|分子靶向', self.text):
            self.fields.targeted_drug_covered = True
        
        # CAR-T
        if re.search(r'CAR-T|cart|细胞免疫治疗|嵌合抗原受体', self.text):
            self.fields.car_t_covered = True
        
        # 指定药品清单
        if re.search(r'药品清单|特定药品目录|指定药品', self.text):
            self.fields.designated_drug_list_required = True
    
    def _extract_special_services(self):
        """抽取增值服务"""
        # 绿色通道
        if re.search(r'绿色通道|绿通|就医绿通|专家预约', self.text):
            self.fields.green_channel_covered = True
        
        # 直付服务
        if re.search(r'直付|直接结算|垫付|医疗直付', self.text):
            self.fields.claim_direct_billing_available = True
    
    def _extract_emergency_overseas(self):
        """抽取紧急情况和海外就医"""
        # 紧急情况医院等级例外
        if re.search(r'紧急.*?(?:不受|突破).*?等级|急救.*?(?:不限|任何医院)', self.text):
            self.fields.emergency_hospital_exception = True
        
        # 海外就医
        if re.search(r'海外就医|境外医疗|国外治疗|港澳台', self.text):
            self.fields.overseas_treatment_covered = True
        
        # 停售转保权
        if re.search(r'停售.*?(?:可转保|转投)|产品停售.*?(?:转保|续保)', self.text):
            self.fields.post_stop_transfer_right = True


def extract_text_from_pdf(pdf_path: str) -> str:
    """从PDF文件中提取文本内容"""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def extract_policy_fields(pdf_path: str) -> InsurancePolicyFields:
    """
    从PDF保险条款中抽取所有字段
    
    Args:
        pdf_path: PDF文件路径
        
    Returns:
        InsurancePolicyFields: 包含所有抽取字段的数据对象
    """
    text = extract_text_from_pdf(pdf_path)
    extractor = InsurancePolicyExtractor(text)
    return extractor.extract_all()


def format_field_value(value: Any) -> str:
    """格式化字段值用于显示"""
    if value is None:
        return "未识别"
    elif isinstance(value, bool):
        return "✓ 是" if value else "✗ 否"
    elif isinstance(value, float):
        if value <= 1.0 and value > 0:  # 比例
            return f"{value:.0%}"
        return f"{value:,.2f}"
    elif isinstance(value, int):
        if value == 100:  # 终身
            return "终身"
        return str(value)
    return str(value)


def generate_comparison_report(fields: InsurancePolicyFields, output_format: str = "markdown") -> str:
    """
    生成字段抽取报告
    
    Args:
        fields: 抽取的字段数据
        output_format: 输出格式 (markdown/json)
        
    Returns:
        str: 格式化的报告字符串
    """
    if output_format == "json":
        return json.dumps(asdict(fields), ensure_ascii=False, indent=2)
    
    # Markdown 格式
    lines = []
    lines.append("# 保险条款字段抽取报告")
    lines.append("")
    
    # 基本信息
    lines.append("## 📋 产品基本信息")
    lines.append("")
    lines.append(f"**产品名称**: {fields.product_name or '未识别'}")
    lines.append(f"**保险公司**: {fields.insurance_company or '未识别'}")
    lines.append("")
    
    # Level 1 字段
    lines.append("## 🎯 Level 1: 绝对核心字段")
    lines.append("")
    lines.append("### 💰 保额与免赔")
    lines.append(f"| 年度总限额 | {format_field_value(fields.total_annual_limit)} |")
    lines.append(f"| 免赔额 | {format_field_value(fields.deductible_amount)} |")
    lines.append(f"| 免赔额单位 | {format_field_value(fields.deductible_unit)} |")
    lines.append("")
    
    lines.append("### 📊 赔付比例")
    lines.append(f"| 有社保赔付比例 | {format_field_value(fields.reimbursement_ratio_with_social_security)} |")
    lines.append(f"| 无社保赔付比例 | {format_field_value(fields.reimbursement_ratio_without_social_security)} |")
    lines.append("")
    
    lines.append("### 🔄 续保条款")
    lines.append(f"| 保证续保 | {format_field_value(fields.renewal_guaranteed)} |")
    lines.append(f"| 保证续保年限 | {format_field_value(fields.renewal_guarantee_years)} |")
    lines.append(f"| 续保需健康告知 | {format_field_value(fields.renewal_requires_health_recheck)} |")
    lines.append(f"| 费率调整上限 | {format_field_value(fields.premium_adjustment_cap)} |")
    lines.append("")
    
    lines.append("### 🏥 医院要求")
    lines.append(f"| 医院等级要求 | {format_field_value(fields.hospital_level_requirement)} |")
    lines.append(f"| 仅限公立医院 | {format_field_value(fields.public_hospital_required)} |")
    lines.append("")
    
    lines.append("### ⏱️ 等待期与基础责任")
    lines.append(f"| 等待期 | {format_field_value(fields.waiting_period_days)} |")
    lines.append(f"| 住院医疗保障 | {format_field_value(fields.inpatient_medical_covered)} |")
    lines.append(f"| 药品保障范围 | {format_field_value(fields.drug_coverage_scope)} |")
    lines.append(f"| 院外购药 | {format_field_value(fields.out_of_hospital_drug_covered)} |")
    lines.append(f"| 质子重离子 | {format_field_value(fields.proton_heavy_ion_covered)} |")
    lines.append("")
    
    # Level 2 字段
    lines.append("## 🔍 Level 2: 对比增强字段")
    lines.append("")
    lines.append("### 👨‍👩‍👧‍👦 家庭特性")
    lines.append(f"| 家庭共享免赔额 | {format_field_value(fields.deductible_family_shared)} |")
    lines.append(f"| 医保抵扣免赔额 | {format_field_value(fields.social_security_offset_allowed)} |")
    lines.append(f"| 支持家庭单 | {format_field_value(fields.family_plan_available)} |")
    lines.append("")
    
    lines.append("### 🏥 门诊保障")
    lines.append(f"| 特殊门诊 | {format_field_value(fields.special_outpatient_covered)} |")
    lines.append(f"| 门诊手术 | {format_field_value(fields.outpatient_surgery_covered)} |")
    lines.append(f"| 住院前后门急诊 | {format_field_value(fields.pre_post_hospital_outpatient_days)} |")
    lines.append("")
    
    lines.append("### 🎯 重疾特性")
    lines.append(f"| 重疾0免赔 | {format_field_value(fields.critical_disease_deductible_zero)} |")
    lines.append(f"| 重疾独立保额 | {format_field_value(fields.critical_disease_separate_limit)} |")
    lines.append("")
    
    lines.append("### 💊 药品特性")
    lines.append(f"| 靶向药 | {format_field_value(fields.targeted_drug_covered)} |")
    lines.append(f"| CAR-T治疗 | {format_field_value(fields.car_t_covered)} |")
    lines.append(f"| 需指定药品清单 | {format_field_value(fields.designated_drug_list_required)} |")
    lines.append("")
    
    lines.append("### ✨ 增值服务")
    lines.append(f"| 绿色通道 | {format_field_value(fields.green_channel_covered)} |")
    lines.append(f"| 直付服务 | {format_field_value(fields.claim_direct_billing_available)} |")
    lines.append("")
    
    lines.append("### 🌍 特殊情况")
    lines.append(f"| 紧急医院例外 | {format_field_value(fields.emergency_hospital_exception)} |")
    lines.append(f"| 海外就医 | {format_field_value(fields.overseas_treatment_covered)} |")
    lines.append(f"| 停售转保权 | {format_field_value(fields.post_stop_transfer_right)} |")
    lines.append("")
    
    return "\n".join(lines)


def run(pdf_path_1: str, pdf_path_2: str = None, output_path: str = "insurance_analysis.md") -> str:
    """
    主运行函数 - 兼容原有接口
    
    Args:
        pdf_path_1: 第一个PDF文件路径
        pdf_path_2: 第二个PDF文件路径（可选，用于对比）
        output_path: 输出文件路径
        
    Returns:
        str: 操作结果信息
    """
    if not Path(pdf_path_1).exists():
        return f"❌ 文件不存在: {pdf_path_1}"
    
    try:
        # 抽取第一个文件的字段
        fields1 = extract_policy_fields(pdf_path_1)
        report = generate_comparison_report(fields1)
        
        # 如果有第二个文件，进行对比
        if pdf_path_2:
            if not Path(pdf_path_2).exists():
                return f"❌ 文件不存在: {pdf_path_2}"
            
            fields2 = extract_policy_fields(pdf_path_2)
            report += "\n\n---\n\n"
            report += generate_comparison_report(fields2)
            report = report.replace("# 保险条款字段抽取报告", "# 保险条款对比报告\n\n## 产品A")
            report = report.replace("## 📋 产品基本信息", "## 产品B\n\n### 📋 产品基本信息", 1)
        
        # 保存报告
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        return f"✅ 分析完成，已生成报告: {output_path}"
        
    except Exception as e:
        return f"❌ 处理过程中出错: {str(e)}"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python extract_insurance_v2.py <pdf文件1> [pdf文件2] [输出文件]")
        print("示例: python extract_insurance_v2.py policy_a.pdf")
        print("       python extract_insurance_v2.py policy_a.pdf policy_b.pdf comparison.md")
        sys.exit(1)
    
    pdf1 = sys.argv[1]
    pdf2 = sys.argv[2] if len(sys.argv) > 2 else None
    output = sys.argv[3] if len(sys.argv) > 3 else "insurance_analysis.md"
    
    result = run(pdf1, pdf2, output)
    print(result)
