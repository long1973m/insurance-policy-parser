#!/usr/bin/env python3
"""
Layer 1: 文本预处理技能
职责：PDF转文本、表格抽取、章节切分
输出：结构化章节块
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

try:
    from PyPDF2 import PdfReader
except ImportError:
    raise ImportError("请先安装 PyPDF2: pip install PyPDF2")


@dataclass
class Section:
    """章节数据结构"""
    title: str
    start_page: int
    end_page: int
    text: str
    level: int = 1  # 章节层级


@dataclass
class Table:
    """表格数据结构"""
    page: int
    content: List[List[str]]
    caption: Optional[str] = None


@dataclass
class PreprocessingResult:
    """预处理结果"""
    sections: Dict[str, Section]
    tables: List[Table]
    metadata: Dict[str, any]
    raw_text: str


class TextPreprocessor:
    """
    文本预处理器
    
    功能：
    1. PDF转文本
    2. 识别并切分章节
    3. 提取表格（基础版）
    4. 生成结构化数据
    """
    
    # 常见的章节标题模式（保险条款）
    SECTION_PATTERNS = [
        # 标准格式：1. 保险责任 或 1.1 保险责任
        r'^\s*(\d+(?:\.\d+)?)\s*([\u4e00-\u9fa5]+(?:条款|责任|范围|说明))\s*$',
        # 带符号格式：【保险责任】
        r'^\s*[【\[]([^【\]]+)[】\]]\s*$',
        # 粗体格式：**保险责任**
        r'^\s*\*\*([^\*]+)\*\*\s*$',
    ]
    
    # 关键章节关键词映射
    KEY_SECTIONS = {
        '保险责任': ['保险责任', '保障范围', '我们保什么'],
        '续保条款': ['续保', '保证续保', '续保期间'],
        '医疗机构': ['医院', '医疗机构', '就诊医院'],
        '责任免除': ['责任免除', '免责', '我们不承担'],
        '等待期': ['等待期', '观察期'],
        '免赔额': ['免赔额', ' deductible'],
        '赔付比例': ['给付比例', '赔付比例', '报销比例'],
        '投保规则': ['投保年龄', '投保范围', '谁能保'],
    }
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.reader = PdfReader(pdf_path)
        self.pages_text = []
        self.full_text = ""
        
    def preprocess(self) -> PreprocessingResult:
        """
        执行完整的预处理流程
        
        Returns:
            PreprocessingResult: 包含章节、表格、元数据的结构化结果
        """
        # Step 1: 提取所有页面文本
        self._extract_all_pages()
        
        # Step 2: 识别章节边界
        sections = self._split_sections()
        
        # Step 3: 提取表格（简化版）
        tables = self._extract_tables_simple()
        
        # Step 4: 收集元数据
        metadata = self._collect_metadata()
        
        return PreprocessingResult(
            sections=sections,
            tables=tables,
            metadata=metadata,
            raw_text=self.full_text
        )
    
    def _extract_all_pages(self):
        """提取所有页面的文本"""
        for i, page in enumerate(self.reader.pages, 1):
            text = page.extract_text() or ""
            self.pages_text.append({
                'page_num': i,
                'text': text
            })
        
        # 合并完整文本，保留页码标记用于定位
        self.full_text = "\n".join([
            f"\n--- PAGE {p['page_num']} ---\n{p['text']}"
            for p in self.pages_text
        ])
    
    def _split_sections(self) -> Dict[str, Section]:
        """
        将文本切分为章节
        
        策略：
        1. 识别所有潜在的章节标题
        2. 根据标题位置划分章节边界
        3. 合并相邻的同类型内容
        """
        sections = {}
        
        # 查找所有章节标题位置
        section_boundaries = []
        lines = self.full_text.split('\n')
        current_page = 1
        
        for line_num, line in enumerate(lines):
            # 更新当前页码
            page_match = re.search(r'--- PAGE (\d+) ---', line)
            if page_match:
                current_page = int(page_match.group(1))
                continue
            
            # 尝试匹配章节标题
            for pattern in self.SECTION_PATTERNS:
                match = re.match(pattern, line.strip())
                if match:
                    # 提取标题
                    if len(match.groups()) >= 2:
                        title = match.group(2).strip()
                    else:
                        title = match.group(1).strip()
                    
                    section_boundaries.append({
                        'title': title,
                        'line_num': line_num,
                        'page': current_page
                    })
                    break
        
        # 如果没有找到章节，尝试使用关键词分割
        if not section_boundaries:
            section_boundaries = self._find_sections_by_keywords(lines)
        
        # 根据边界划分章节内容
        for i, boundary in enumerate(section_boundaries):
            title = boundary['title']
            start_line = boundary['line_num']
            start_page = boundary['page']
            
            # 确定结束位置
            if i < len(section_boundaries) - 1:
                end_line = section_boundaries[i + 1]['line_num']
                end_page = section_boundaries[i + 1]['page']
            else:
                end_line = len(lines)
                end_page = len(self.reader.pages)
            
            # 提取章节文本
            section_text = '\n'.join(lines[start_line:end_line])
            
            # 清理页码标记
            section_text = re.sub(r'\n--- PAGE \d+ ---\n', '\n', section_text)
            
            # 标准化标题（映射到关键章节）
            normalized_title = self._normalize_section_title(title)
            
            sections[normalized_title] = Section(
                title=title,
                start_page=start_page,
                end_page=end_page,
                text=section_text.strip(),
                level=1
            )
        
        return sections
    
    def _find_sections_by_keywords(self, lines: List[str]) -> List[Dict]:
        """通过关键词查找章节边界（备用方案）"""
        boundaries = []
        current_page = 1
        
        for line_num, line in enumerate(lines):
            page_match = re.search(r'--- PAGE (\d+) ---', line)
            if page_match:
                current_page = int(page_match.group(1))
                continue
            
            # 检查是否包含关键章节标题
            for standard_name, keywords in self.KEY_SECTIONS.items():
                for keyword in keywords:
                    if keyword in line and len(line.strip()) < 50:  # 标题通常较短
                        boundaries.append({
                            'title': standard_name,
                            'line_num': line_num,
                            'page': current_page
                        })
                        break
        
        return boundaries
    
    def _normalize_section_title(self, title: str) -> str:
        """标准化章节标题"""
        for standard_name, keywords in self.KEY_SECTIONS.items():
            for keyword in keywords:
                if keyword in title:
                    return standard_name
        return title
    
    def _extract_tables_simple(self) -> List[Table]:
        """
        简单表格提取（基于文本分析）
        
        注意：这是简化版，复杂表格建议使用 pdfplumber
        """
        tables = []
        
        # 查找可能的表格区域（连续的多行数字或对齐文本）
        lines = self.full_text.split('\n')
        table_start = None
        table_lines = []
        
        for i, line in enumerate(lines):
            # 检测表格特征：包含多个空格分隔的内容或百分比/金额
            if re.search(r'\d+[.%]?\s+\d+[.%]?|\d{2,}\s*元|\d+%', line):
                if table_start is None:
                    table_start = i
                table_lines.append(line)
            else:
                # 表格结束
                if table_lines and len(table_lines) >= 3:  # 至少3行才认为是表格
                    # 尝试解析为表格
                    rows = [line.split() for line in table_lines]
                    if all(len(row) == len(rows[0]) for row in rows):  # 列数一致
                        tables.append(Table(
                            page=1,  # 简化处理
                            content=rows,
                            caption=None
                        ))
                table_start = None
                table_lines = []
        
        return tables
    
    def _collect_metadata(self) -> Dict[str, any]:
        """收集文档元数据"""
        metadata = {
            'total_pages': len(self.reader.pages),
            'filename': Path(self.pdf_path).name,
        }
        
        # 尝试提取保险公司名称
        company_patterns = [
            r'([\u4e00-\u9fa5]+人寿保险有限公司)',
            r'([\u4e00-\u9fa5]+财产保险股份有限公司)',
            r'([\u4e00-\u9fa5]+养老保险股份有限公司)',
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, self.full_text[:5000])  # 只在前几页查找
            if match:
                metadata['company'] = match.group(1)
                break
        
        # 尝试提取产品名称
        product_match = re.search(r'(\S+?医疗保险.*?条款)', self.full_text[:5000])
        if product_match:
            metadata['product_name'] = product_match.group(1)
        
        return metadata
    
    def get_section(self, section_name: str) -> Optional[str]:
        """
        获取指定章节的文本
        
        Args:
            section_name: 章节名称（如"保险责任"、"续保条款"）
            
        Returns:
            Optional[str]: 章节文本，如果不存在返回None
        """
        result = self.preprocess()
        
        # 直接匹配
        if section_name in result.sections:
            return result.sections[section_name].text
        
        # 模糊匹配
        for key, section in result.sections.items():
            if section_name in key or key in section_name:
                return section.text
        
        return None


def preprocess_pdf(pdf_path: str) -> Dict:
    """
    便捷的PDF预处理函数
    
    Args:
        pdf_path: PDF文件路径
        
    Returns:
        Dict: 可序列化的预处理结果
    """
    preprocessor = TextPreprocessor(pdf_path)
    result = preprocessor.preprocess()
    
    # 转换为可序列化的字典
    return {
        'sections': {
            name: {
                'title': section.title,
                'start_page': section.start_page,
                'end_page': section.end_page,
                'text': section.text[:1000] + '...' if len(section.text) > 1000 else section.text,
                'level': section.level,
                'text_length': len(section.text)
            }
            for name, section in result.sections.items()
        },
        'metadata': result.metadata,
        'statistics': {
            'total_sections': len(result.sections),
            'total_tables': len(result.tables),
            'total_pages': result.metadata.get('total_pages', 0),
            'total_chars': len(result.raw_text)
        }
    }


if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("用法: python layer1_text_preprocessor.py <pdf文件> [输出json文件]")
        print("示例: python layer1_text_preprocessor.py policy.pdf sections.json")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "preprocessing_result.json"
    
    result = preprocess_pdf(pdf_path)
    
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 预处理完成！")
    print(f"📄 发现 {result['statistics']['total_sections']} 个章节")
    print(f"📊 共 {result['statistics']['total_pages']} 页，{result['statistics']['total_chars']} 字符")
    print(f"💾 结果已保存: {output}")
