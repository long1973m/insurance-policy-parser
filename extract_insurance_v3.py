#!/usr/bin/env python3
"""
保险条款核心字段抽取工具 V3
基于标准化字段表格，从PDF保险条款中抽取结构化数据
输出纯JSON格式，包含每个字段的原始文本来源
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict

try:
    from PyPDF2 import PdfReader
except ImportError:
    raise ImportError("请先安装 PyPDF2: pip install PyPDF2")


@dataclass
class FieldResult:
    """字段抽取结果"""
    value: Any
    source_text: Optional[str] = None


class InsurancePolicyExtractor:
    """保险条款字段抽取器 - V3版本"""
    
    def __init__(self, text: str):
        self.text = text
        self.results: Dict[str, FieldResult] = {}
    
    def extract_all(self) -> Dict[str, FieldResult]:
        """抽取所有字段并返回结构化结果"""
        self._extract_level1_fields()
        self._extract_level2_fields()
        return self.results
    
    def _add_result(self, field_name: str, value: Any, source_text: Optional[str] = None):
        """添加字段抽取结果"""
        self.results[field_name] = FieldResult(value=value, source_text=source_text)
    
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
            (r'(\S+?医疗保险.*?条款)', '产品名称'),
            (r'(\S+?重疾险.*?条款)', '产品名称'),
            (r'(\S+?意外险.*?条款)', '产品名称'),
            (r'([\u4e00-\u9fa5]+保险[^\n]{0,20}条款)', '产品名称'),
        ]
        for pattern, desc in name_patterns:
            match = re.search(pattern, self.text)
            if match:
                self._add_result('product_name', match.group(1).strip(), match.group(0))
                break
        else:
            self._add_result('product_name', None)
        
        # 保险公司
        company_patterns = [
            (r'([\u4e00-\u9fa5]+人寿保险有限公司)', '保险公司'),
            (r'([\u4e00-\u9fa5]+财产保险股份有限公司)', '保险公司'),
            (r'([\u4e00-\u9fa5]+养老保险股份有限公司)', '保险公司'),
        ]
        for pattern, desc in company_patterns:
            match = re.search(pattern, self.text)
            if match:
                self._add_result('insurance_company', match.group(1).strip(), match.group(0))
                break
        else:
            self._add_result('insurance_company', None)
    
    def _extract_annual_limit(self):
        """抽取年度总赔付限额"""
        patterns = [
            (r'年度.*?(?:限额|保额).*?(\d{1,3}(?:,\d{3})*)\s*万', '年度限额'),
            (r'最高.*?(?:赔付|给付).*?(\d{1,3}(?:,\d{3})*)\s*万', '最高赔付'),
            (r'保险金额[为：:]?(\d{1,3}(?:,\d{3})*)\s*万', '保险金额'),
            (r'年度累计.*?([\d,]+)\s*万元', '年度累计'),
        ]
        
        for pattern, desc in patterns:
            match = re.search(pattern, self.text)
            if match:
                amount_str = match.group(1).replace(',', '')
                amount = float(amount_str) * 10000
                self._add_result('total_annual_limit', amount, match.group(0))
                return
        
        # 尝试从保险责任部分查找
        coverage_section = re.search(r'保险责任[\s\S]{0,2000}', self.text)
        if coverage_section:
            section_text = coverage_section.group()
            amount_matches = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*万', section_text)
            valid_amounts = []
            for amt_str in amount_matches:
                amt = int(amt_str.replace(',', ''))
                if 100 <= amt <= 1000:
                    valid_amounts.append(amt)
            if valid_amounts:
                max_amount = max(valid_amounts) * 10000
                self._add_result('total_annual_limit', max_amount, f"保险责任段落中找到保额: {max(valid_amounts)}万")
                return
        
        self._add_result('total_annual_limit', None)
    
    def _extract_deductible(self):
        """抽取免赔额信息"""
        # 免赔额金额
        patterns = [
            (r'免赔额[为：:]?(\d{1,3}(?:,\d{3})*)\s*元', '免赔额'),
            (r'免赔额.*?([\d,]+)\s*元', '免赔额'),
            (r'([\d,]+)\s*元.*?(?:年)?度免赔额', '年度免赔额'),
        ]
        
        for pattern, desc in patterns:
            match = re.search(pattern, self.text)
            if match:
                amount_str = match.group(1).replace(',', '')
                amount = float(amount_str)
                self._add_result('deductible_amount', amount, match.group(0))
                break
        else:
            self._add_result('deductible_amount', None)
        
        # 免赔额单位
        unit_patterns = [
            (r'(?:每)?年[度]?免赔额', '年'),
            (r'每次免赔额', '次'),
            (r'每疾病免赔额', '疾病'),
            (r'每住院免赔额', '住院'),
        ]
        
        for pattern, unit in unit_patterns:
            match = re.search(pattern, self.text)
            if match:
                self._add_result('deductible_unit', unit, match.group(0))
                break
        else:
            if self.results.get('deductible_amount') and self.results['deductible_amount'].value:
                self._add_result('deductible_unit', '年', '默认年度')
            else:
                self._add_result('deductible_unit', None)
    
    def _extract_reimbursement_ratios(self):
        """抽取赔付比例"""
        # 有社保/无社保比例
        ss_patterns = [
            (r'(?:以有社保身份|有社保|经社保|已参加社保)[\s\S]{0,300}?(\d{1,3})%', '有社保'),
            (r'(?:给付比例|赔付比例)[^。]*?(?:社保|医保)[^。]*?(\d{1,3})%', '有社保比例'),
        ]
        no_ss_patterns = [
            (r'(?:未以有社保|无社保|未经社保|未参加社保)[\s\S]{0,300}?(\d{1,3})%', '无社保'),
            (r'(?:给付比例|赔付比例)[^。]*?(?:未经|无|未参加)[^。]*?(\d{1,3})%', '无社保比例'),
        ]
        
        ss_found = False
        for pattern, desc in ss_patterns:
            match = re.search(pattern, self.text)
            if match:
                pct = int(match.group(1))
                if 30 <= pct <= 100:
                    self._add_result('reimbursement_ratio_with_social_security', pct / 100, match.group(0))
                    ss_found = True
                    break
        if not ss_found:
            self._add_result('reimbursement_ratio_with_social_security', None)
        
        no_ss_found = False
        for pattern, desc in no_ss_patterns:
            match = re.search(pattern, self.text)
            if match:
                pct = int(match.group(1))
                if 30 <= pct <= 100:
                    self._add_result('reimbursement_ratio_without_social_security', pct / 100, match.group(0))
                    no_ss_found = True
                    break
        if not no_ss_found:
            self._add_result('reimbursement_ratio_without_social_security', None)
    
    def _extract_renewal_terms(self):
        """抽取续保条款"""
        # 保证续保
        if re.search(r'保证续保|承诺续保|可保证续保', self.text):
            match = re.search(r'.{0,50}(?:保证续保|承诺续保).{0,50}', self.text)
            self._add_result('renewal_guaranteed', True, match.group(0) if match else '包含保证续保条款')
        elif re.search(r'不保证续保|非保证续保', self.text):
            match = re.search(r'.{0,50}(?:不保证续保|非保证续保).{0,50}', self.text)
            self._add_result('renewal_guaranteed', False, match.group(0) if match else '不包含保证续保')
        else:
            self._add_result('renewal_guaranteed', None)
        
        # 保证续保年限
        year_patterns = [
            (r'保证续保\s*(\d+)\s*年', '保证续保年数'),
            (r'(\d+)\s*年保证续保', '年保证续保'),
            (r'保证续保期间[为：:]?(\d+)\s*年', '保证续保期间'),
            (r'每\s*(\d+)\s*年为一个保证续保期间', '每N年保证续保'),
        ]
        
        for pattern, desc in year_patterns:
            match = re.search(pattern, self.text)
            if match:
                years = int(match.group(1))
                self._add_result('renewal_guarantee_years', years, match.group(0))
                break
        else:
            if re.search(r'终身保证续保|保证续保.*终身', self.text):
                self._add_result('renewal_guarantee_years', 100, '终身保证续保')
            else:
                self._add_result('renewal_guarantee_years', None)
        
        # 续保是否需重新健康告知
        if re.search(r'续保.*?(?:无需|不需|不用).*?(?:健康告知|告知)', self.text):
            match = re.search(r'.{0,80}续保.*?(?:无需|不需|不用).*?(?:健康告知|告知).{0,20}', self.text)
            self._add_result('renewal_requires_health_recheck', False, match.group(0) if match else '续保无需健康告知')
        elif re.search(r'续保.*?(?:需要|须|应).*?(?:健康告知|告知|核保)', self.text):
            match = re.search(r'.{0,80}续保.*?(?:需要|须|应).*?(?:健康告知|告知|核保).{0,20}', self.text)
            self._add_result('renewal_requires_health_recheck', True, match.group(0) if match else '续保需要健康告知')
        else:
            self._add_result('renewal_requires_health_recheck', None)
        
        # 费率调整上限
        cap_match = re.search(r'费率调整.*?上限[为：:]?(\d+)%', self.text)
        if cap_match:
            self._add_result('premium_adjustment_cap', int(cap_match.group(1)) / 100, cap_match.group(0))
        else:
            self._add_result('premium_adjustment_cap', None)
    
    def _extract_hospital_requirements(self):
        """抽取医院要求"""
        # 医院等级
        if re.search(r'三级(?:及)?以上|三甲', self.text):
            match = re.search(r'.{0,30}三级(?:及)?以上.{0,20}', self.text)
            self._add_result('hospital_level_requirement', '三级及以上', match.group(0) if match else '三级及以上医院')
        elif re.search(r'二级(?:及)?以上', self.text):
            match = re.search(r'.{0,30}二级(?:及)?以上.{0,20}', self.text)
            self._add_result('hospital_level_requirement', '二级及以上', match.group(0) if match else '二级及以上医院')
        elif re.search(r'一级(?:及)?以上', self.text):
            match = re.search(r'.{0,30}一级(?:及)?以上.{0,20}', self.text)
            self._add_result('hospital_level_requirement', '一级及以上', match.group(0) if match else '一级及以上医院')
        elif re.search(r'不限等级|无等级限制|各级医院', self.text):
            match = re.search(r'.{0,30}(?:不限等级|无等级限制).{0,20}', self.text)
            self._add_result('hospital_level_requirement', '无限制', match.group(0) if match else '不限医院等级')
        else:
            self._add_result('hospital_level_requirement', None)
        
        # 是否仅限公立
        if re.search(r'公立|医保定点', self.text) and not re.search(r'私立|民营', self.text):
            match = re.search(r'.{0,30}公立.{0,20}', self.text)
            self._add_result('public_hospital_required', True, match.group(0) if match else '公立医院')
        elif re.search(r'私立|民营.*?(?:可赔|包含|涵盖)', self.text):
            match = re.search(r'.{0,30}私立.{0,20}', self.text)
            self._add_result('public_hospital_required', False, match.group(0) if match else '包含私立医院')
        else:
            self._add_result('public_hospital_required', None)
    
    def _extract_waiting_period(self):
        """抽取等待期"""
        patterns = [
            (r'等待期[为：:]?(\d+)\s*天', '等待期天数'),
            (r'(\d+)\s*天.*?(?:为)?等待期', '天等待期'),
            (r'观察期[为：:]?(\d+)\s*天', '观察期'),
        ]
        
        for pattern, desc in patterns:
            match = re.search(pattern, self.text)
            if match:
                self._add_result('waiting_period_days', int(match.group(1)), match.group(0))
                break
        else:
            self._add_result('waiting_period_days', None)
    
    def _extract_basic_coverage(self):
        """抽取基础保障责任"""
        # 住院医疗
        if re.search(r'一般住院医疗|住院医疗保险金|住院医疗费用', self.text):
            match = re.search(r'.{0,50}(?:一般住院医疗|住院医疗保险金).{0,30}', self.text)
            self._add_result('inpatient_medical_covered', True, match.group(0) if match else '包含住院医疗')
        else:
            self._add_result('inpatient_medical_covered', None)
        
        # 药品保障范围
        if re.search(r'社保目录内|医保目录内|国家医保', self.text):
            match = re.search(r'.{0,50}(?:社保目录内|医保目录内).{0,20}', self.text)
            self._add_result('drug_coverage_scope', '社保目录内', match.group(0) if match else '社保目录内')
        elif re.search(r'药品清单|特定药品清单', self.text):
            match = re.search(r'.{0,50}药品清单.{0,20}', self.text)
            self._add_result('drug_coverage_scope', '药品保障清单内', match.group(0) if match else '药品保障清单内')
        elif re.search(r'全部药品|所有药品|合理且必要', self.text):
            match = re.search(r'.{0,50}(?:全部药品|所有药品).{0,20}', self.text)
            self._add_result('drug_coverage_scope', '全部', match.group(0) if match else '全部药品')
        else:
            self._add_result('drug_coverage_scope', '未明确')
        
        # 院外购药
        if re.search(r'院外特定药品|外购药|院外购药|DTP药房', self.text):
            match = re.search(r'.{0,50}(?:院外特定药品|外购药).{0,30}', self.text)
            self._add_result('out_of_hospital_drug_covered', True, match.group(0) if match else '包含院外购药')
        elif re.search(r'不含院外|院外.*?(?:不赔|除外)', self.text):
            match = re.search(r'.{0,50}不含院外.{0,20}', self.text)
            self._add_result('out_of_hospital_drug_covered', False, match.group(0) if match else '不含院外购药')
        else:
            self._add_result('out_of_hospital_drug_covered', None)
    
    def _extract_advanced_treatments(self):
        """抽取高端治疗项目"""
        # 质子重离子
        if re.search(r'质子重离子|质子、重离子|质子治疗', self.text):
            match = re.search(r'.{0,50}(?:质子重离子|质子治疗).{0,30}', self.text)
            self._add_result('proton_heavy_ion_covered', True, match.group(0) if match else '包含质子重离子')
        elif re.search(r'不含质子|质子.*?(?:不赔|除外)', self.text):
            match = re.search(r'.{0,50}不含质子.{0,20}', self.text)
            self._add_result('proton_heavy_ion_covered', False, match.group(0) if match else '不含质子重离子')
        else:
            self._add_result('proton_heavy_ion_covered', None)
    
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
            match = re.search(r'.{0,50}家庭共享免赔额.{0,30}', self.text)
            self._add_result('deductible_family_shared', True, match.group(0) if match else '家庭共享免赔额')
        else:
            self._add_result('deductible_family_shared', None)
        
        # 医保抵扣免赔额
        if re.search(r'医保报销.*抵扣免赔额|社保.*抵扣|医保.*计入免赔额', self.text):
            match = re.search(r'.{0,50}(?:医保报销.*抵扣|社保.*抵扣).{0,30}', self.text)
            self._add_result('social_security_offset_allowed', True, match.group(0) if match else '医保可抵扣免赔额')
        else:
            self._add_result('social_security_offset_allowed', None)
        
        # 家庭单投保
        if re.search(r'家庭单|家庭成员.*投保|家属.*投保', self.text):
            match = re.search(r'.{0,50}(?:家庭单|家庭成员.*投保).{0,30}', self.text)
            self._add_result('family_plan_available', True, match.group(0) if match else '支持家庭单')
        else:
            self._add_result('family_plan_available', None)
    
    def _extract_outpatient_features(self):
        """抽取门诊相关特性"""
        # 特殊门诊
        if re.search(r'特殊门诊|门诊肾透析|门诊放化疗|器官移植后抗排异', self.text):
            match = re.search(r'.{0,50}(?:特殊门诊|门诊肾透析).{0,30}', self.text)
            self._add_result('special_outpatient_covered', True, match.group(0) if match else '包含特殊门诊')
        else:
            self._add_result('special_outpatient_covered', None)
        
        # 门诊手术
        if re.search(r'门诊手术|日间手术', self.text):
            match = re.search(r'.{0,50}(?:门诊手术|日间手术).{0,30}', self.text)
            self._add_result('outpatient_surgery_covered', True, match.group(0) if match else '包含门诊手术')
        else:
            self._add_result('outpatient_surgery_covered', None)
        
        # 住院前后门急诊天数
        patterns = [
            (r'住院前\s*(\d+)\s*日?及?.*?出院后\s*(\d+)\s*日', 'sum'),
            (r'住院前\s*(\d+)\s*天.*住院后\s*(\d+)\s*天', 'sum'),
            (r'住院前后各\s*(\d+)\s*天', 'each'),
        ]
        
        for pattern, calc_type in patterns:
            match = re.search(pattern, self.text)
            if match:
                if calc_type == 'sum':
                    days = int(match.group(1)) + int(match.group(2))
                else:
                    days = int(match.group(1)) * 2
                self._add_result('pre_post_hospital_outpatient_days', days, match.group(0))
                break
        else:
            self._add_result('pre_post_hospital_outpatient_days', None)
    
    def _extract_critical_disease_features(self):
        """抽取重疾相关特性"""
        # 重疾0免赔
        if re.search(r'重疾.*0免赔|重大疾病.*零免赔|重疾.*无免赔', self.text):
            match = re.search(r'.{0,50}(?:重疾.*0免赔|重大疾病.*零免赔).{0,30}', self.text)
            self._add_result('critical_disease_deductible_zero', True, match.group(0) if match else '重疾0免赔')
        else:
            self._add_result('critical_disease_deductible_zero', None)
        
        # 重疾独立保额
        if re.search(r'重疾.*单独限额|重大疾病.*独立保额|重疾.*不占用', self.text):
            match = re.search(r'.{0,50}(?:重疾.*单独限额|重大疾病.*独立保额).{0,30}', self.text)
            self._add_result('critical_disease_separate_limit', True, match.group(0) if match else '重疾独立保额')
        else:
            self._add_result('critical_disease_separate_limit', None)
    
    def _extract_drug_features(self):
        """抽取药品相关特性"""
        # 靶向药
        if re.search(r'靶向药|靶向治疗|分子靶向', self.text):
            match = re.search(r'.{0,50}(?:靶向药|靶向治疗).{0,30}', self.text)
            self._add_result('targeted_drug_covered', True, match.group(0) if match else '包含靶向药')
        else:
            self._add_result('targeted_drug_covered', None)
        
        # CAR-T
        if re.search(r'CAR-T|cart|细胞免疫治疗|嵌合抗原受体', self.text):
            match = re.search(r'.{0,50}(?:CAR-T|细胞免疫治疗).{0,30}', self.text)
            self._add_result('car_t_covered', True, match.group(0) if match else '包含CAR-T')
        else:
            self._add_result('car_t_covered', None)
        
        # 指定药品清单
        if re.search(r'药品清单|特定药品目录|指定药品', self.text):
            match = re.search(r'.{0,50}(?:药品清单|特定药品目录).{0,30}', self.text)
            self._add_result('designated_drug_list_required', True, match.group(0) if match else '需指定药品清单')
        else:
            self._add_result('designated_drug_list_required', None)
    
    def _extract_special_services(self):
        """抽取增值服务"""
        # 绿色通道
        if re.search(r'绿色通道|绿通|就医绿通|专家预约', self.text):
            match = re.search(r'.{0,50}(?:绿色通道|绿通).{0,30}', self.text)
            self._add_result('green_channel_covered', True, match.group(0) if match else '包含绿色通道')
        else:
            self._add_result('green_channel_covered', None)
        
        # 直付服务
        if re.search(r'直付|直接结算|垫付|医疗直付', self.text):
            match = re.search(r'.{0,50}(?:直付|直接结算).{0,30}', self.text)
            self._add_result('claim_direct_billing_available', True, match.group(0) if match else '包含直付服务')
        else:
            self._add_result('claim_direct_billing_available', None)
    
    def _extract_emergency_overseas(self):
        """抽取紧急情况和海外就医"""
        # 紧急情况医院等级例外
        if re.search(r'紧急.*?(?:不受|突破).*?等级|急救.*?(?:不限|任何医院)', self.text):
            match = re.search(r'.{0,50}(?:紧急.*突破|急救.*不限).{0,30}', self.text)
            self._add_result('emergency_hospital_exception', True, match.group(0) if match else '紧急情况例外')
        else:
            self._add_result('emergency_hospital_exception', None)
        
        # 海外就医
        if re.search(r'海外就医|境外医疗|国外治疗|港澳台', self.text):
            match = re.search(r'.{0,50}(?:海外就医|境外医疗).{0,30}', self.text)
            self._add_result('overseas_treatment_covered', True, match.group(0) if match else '包含海外就医')
        else:
            self._add_result('overseas_treatment_covered', None)
        
        # 停售转保权
        if re.search(r'停售.*?(?:可转保|转投)|产品停售.*?(?:转保|续保)', self.text):
            match = re.search(r'.{0,50}(?:停售.*转保|产品停售.*转保).{0,30}', self.text)
            self._add_result('post_stop_transfer_right', True, match.group(0) if match else '停售可转保')
        else:
            self._add_result('post_stop_transfer_right', None)


def extract_text_from_pdf(pdf_path: str) -> str:
    """从PDF文件中提取文本内容"""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def extract_policy_to_json(pdf_path: str, indent: int = 2) -> str:
    """
    从PDF保险条款中抽取所有字段，返回JSON格式字符串
    
    Args:
        pdf_path: PDF文件路径
        indent: JSON缩进空格数
        
    Returns:
        str: JSON格式字符串
    """
    text = extract_text_from_pdf(pdf_path)
    extractor = InsurancePolicyExtractor(text)
    results = extractor.extract_all()
    
    # 转换为字典格式
    output = {}
    for field_name, result in results.items():
        output[field_name] = {
            "value": result.value,
            "source_text": result.source_text
        }
    
    return json.dumps(output, ensure_ascii=False, indent=indent)


def extract_policy_to_dict(pdf_path: str) -> Dict[str, Dict[str, Any]]:
    """
    从PDF保险条款中抽取所有字段，返回字典格式
    
    Args:
        pdf_path: PDF文件路径
        
    Returns:
        Dict: 字段结果字典
    """
    text = extract_text_from_pdf(pdf_path)
    extractor = InsurancePolicyExtractor(text)
    results = extractor.extract_all()
    
    output = {}
    for field_name, result in results.items():
        output[field_name] = {
            "value": result.value,
            "source_text": result.source_text
        }
    
    return output


def run(pdf_path_1: str, pdf_path_2: str = None, output_path: str = "insurance_analysis.json") -> str:
    """
    主运行函数 - 兼容原有接口，但输出JSON格式
    
    Args:
        pdf_path_1: 第一个PDF文件路径
        pdf_path_2: 第二个PDF文件路径（可选，用于对比）
        output_path: 输出JSON文件路径
        
    Returns:
        str: 操作结果信息
    """
    if not Path(pdf_path_1).exists():
        return f"❌ 文件不存在: {pdf_path_1}"
    
    try:
        output_data = {
            "product_a": extract_policy_to_dict(pdf_path_1)
        }
        
        if pdf_path_2:
            if not Path(pdf_path_2).exists():
                return f"❌ 文件不存在: {pdf_path_2}"
            output_data["product_b"] = extract_policy_to_dict(pdf_path_2)
        
        # 保存JSON文件
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        return f"✅ 分析完成，已生成JSON文件: {output_path}"
        
    except Exception as e:
        return f"❌ 处理过程中出错: {str(e)}"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python extract_insurance_v3.py <pdf文件> [输出json文件]")
        print("示例: python extract_insurance_v3.py policy.pdf output.json")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "insurance_analysis.json"
    
    result = run(pdf_path, None, output)
    print(result)
