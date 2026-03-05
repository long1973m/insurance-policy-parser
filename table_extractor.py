#!/usr/bin/env python3
"""
表格数据抽取器
专门用于从保险条款的表格中抽取结构化数据（如赔付比例表）
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class TableCell:
    """表格单元格"""
    row: int
    col: int
    text: str


@dataclass
class ExtractedTable:
    """提取的表格"""
    headers: List[str]
    rows: List[List[str]]
    caption: Optional[str]
    page_hint: Optional[int]


class TableExtractor:
    """
    表格抽取器
    
    功能：
    1. 从文本中识别表格结构
    2. 解析赔付比例表
    3. 提取医院等级对应关系
    """
    
    def __init__(self, text: str):
        self.text = text
        self.tables: List[ExtractedTable] = []
    
    def extract_reimbursement_table(self) -> Optional[Dict[str, float]]:
        """
        抽取赔付比例表
        
        Returns:
            Dict[str, float]: {情形描述: 赔付比例}
        """
        # 查找赔付比例相关段落
        reimbursement_section = self._find_reimbursement_section()
        if not reimbursement_section:
            return None
        
        # 尝试解析表格
        ratios = {}
        
        # 模式1: "有社保...100%" 格式
        pattern1 = r'(有(?:基本)?医疗[保险]?身份|经(?:基本)?医疗[保险]?结算).*?(\d{1,3})%'
        matches = re.finditer(pattern1, reimbursement_section, re.IGNORECASE)
        for match in matches:
            context = match.group(1)
            ratio = int(match.group(2)) / 100
            key = 'with_social_security' if '有' in context or '经' in context else 'unknown'
            ratios[key] = ratio
        
        # 模式2: "无社保...60%" 格式
        pattern2 = r'(无(?:基本)?医疗[保险]?身份|未经(?:基本)?医疗[保险]?结算).*?(\d{1,3})%'
        matches = re.finditer(pattern2, reimbursement_section, re.IGNORECASE)
        for match in matches:
            context = match.group(1)
            ratio = int(match.group(2)) / 100
            key = 'without_social_security' if '无' in context or '未经' in context else 'unknown'
            ratios[key] = ratio
        
        # 模式3: 表格行格式 "情形 | 条件 | 给付比例"
        table_pattern = r'(?:情形|条件).*?(\d{1,3})%'
        matches = list(re.finditer(table_pattern, reimbursement_section))
        if len(matches) >= 2:
            # 假设第一个是100%，第二个是60%
            ratios['with_social_security'] = int(matches[0].group(1)) / 100
            ratios['without_social_security'] = int(matches[1].group(1)) / 100
        
        return ratios if ratios else None
    
    def _find_reimbursement_section(self) -> Optional[str]:
        """查找赔付比例相关段落"""
        # 搜索关键词
        keywords = [
            '给付比例',
            '赔付比例',
            '报销比例',
            '有基本医疗保险身份',
            '经基本医疗保险结算',
        ]
        
        # 查找包含这些关键词的上下文
        best_match = None
        best_score = 0
        
        # 将文本分成段落
        paragraphs = self.text.split('\n\n')
        
        for para in paragraphs:
            score = 0
            for keyword in keywords:
                if keyword in para:
                    score += 1
            
            # 如果包含百分比，加分
            if '%' in para:
                score += 2
            
            if score > best_score:
                best_score = score
                best_match = para
        
        # 如果没找到，尝试更大的范围
        if not best_match:
            for keyword in keywords[:3]:  # 前三个主要关键词
                idx = self.text.find(keyword)
                if idx != -1:
                    # 提取前后500字符
                    start = max(0, idx - 200)
                    end = min(len(self.text), idx + 800)
                    return self.text[start:end]
        
        return best_match
    
    def extract_hospital_level_table(self) -> Optional[Dict[str, Any]]:
        """
        抽取医院等级对应表
        
        Returns:
            医院等级要求信息
        """
        # 查找医院等级相关段落
        hospital_section = self._find_hospital_section()
        if not hospital_section:
            return None
        
        result = {
            'level': None,
            'public_only': None,
            'emergency_exception': None,
        }
        
        # 医院等级
        level_patterns = [
            (r'三级(?:及)?以上|三甲', '三级及以上'),
            (r'二级(?:及)?以上', '二级及以上'),
            (r'一级(?:及)?以上', '一级及以上'),
        ]
        
        for pattern, level in level_patterns:
            if re.search(pattern, hospital_section):
                result['level'] = level
                break
        
        # 是否公立
        if re.search(r'公立', hospital_section):
            result['public_only'] = True
        elif re.search(r'私立|民营.*?(?:可|可以)', hospital_section):
            result['public_only'] = False
        
        # 紧急情况例外
        if re.search(r'紧急.*?(?:不受|突破)', hospital_section):
            result['emergency_exception'] = True
        
        return result
    
    def _find_hospital_section(self) -> Optional[str]:
        """查找医院相关段落"""
        keywords = ['医院', '医疗机构', '就诊医院', '治疗医院']
        
        paragraphs = self.text.split('\n\n')
        
        for para in paragraphs:
            for keyword in keywords:
                if keyword in para and len(para) < 1000:  # 不要太长
                    return para
        
        # 全文搜索
        for keyword in keywords[:2]:
            idx = self.text.find(keyword)
            if idx != -1:
                start = max(0, idx - 100)
                end = min(len(self.text), idx + 500)
                return self.text[start:end]
        
        return None
    
    def parse_simple_table(self, table_text: str) -> List[List[str]]:
        """
        解析简单表格（空格或制表符分隔）
        
        Args:
            table_text: 表格文本
            
        Returns:
            二维列表表示的表格
        """
        rows = []
        lines = table_text.strip().split('\n')
        
        for line in lines:
            # 尝试多种分隔方式
            # 方式1: 两个或以上空格
            cells = re.split(r'\s{2,}', line.strip())
            if len(cells) >= 2:
                rows.append([c.strip() for c in cells])
        
        return rows
    
    def extract_from_pdfplumber(self, pdf_path: str) -> List[ExtractedTable]:
        """
        使用pdfplumber提取表格（如果有安装的话）
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            提取的表格列表
        """
        try:
            import pdfplumber
        except ImportError:
            print("pdfplumber未安装，使用文本模式")
            return []
        
        tables = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables()
                
                for table in page_tables:
                    if table and len(table) > 1:
                        headers = table[0] if table else []
                        rows = table[1:] if len(table) > 1 else []
                        
                        tables.append(ExtractedTable(
                            headers=headers,
                            rows=rows,
                            caption=None,
                            page_hint=page_num
                        ))
        
        return tables


def extract_reimbursement_ratios(text: str) -> Dict[str, Any]:
    """
    便捷的赔付比例抽取函数
    
    Args:
        text: 要分析的文本
        
    Returns:
        赔付比例信息
    """
    extractor = TableExtractor(text)
    ratios = extractor.extract_reimbursement_table()
    
    if not ratios:
        return {
            'found': False,
            'with_social_security': None,
            'without_social_security': None,
            'source_text': None,
        }
    
    return {
        'found': True,
        'with_social_security': ratios.get('with_social_security'),
        'without_social_security': ratios.get('without_social_security'),
        'all_ratios': ratios,
        'source_text': extractor._find_reimbursement_section()[:200] if extractor._find_reimbursement_section() else None,
    }


if __name__ == "__main__":
    # 测试数据
    test_text = """
    2.8 给付比例
    
    本合同保险金给付比例详见下表：
    
    情形    给付条件    给付比例
    1   若被保险人在投保时选择以有基本医疗保险身份投保，且就诊时经基本医疗保险结算    保障计划载明的赔付比例的100%
    2   若被保险人在投保时选择以有基本医疗保险身份投保，但就诊时未经基本医疗保险结算    保障计划载明的赔付比例的60%
    
    说明：以上比例为示例，具体以保障计划表为准。
    """
    
    print("🧪 测试表格赔付比例抽取...")
    print("="*60)
    
    result = extract_reimbursement_ratios(test_text)
    
    print(f"\n📊 结果:")
    print(f"  找到数据: {result['found']}")
    if result['found']:
        print(f"  有社保比例: {result['with_social_security']}")
        print(f"  无社保比例: {result['without_social_security']}")
    print(f"\n  来源文本片段:")
    if result['source_text']:
        print(f"  {result['source_text'][:150]}...")
    
    print("\n" + "="*60)
    print("✅ 测试完成！")
