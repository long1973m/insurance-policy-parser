#!/usr/bin/env python3
"""
Layer 1 增强版：改进的文本预处理技能
主要改进：
1. 更智能的章节切分（基于标题层级和内容长度）
2. 支持多级章节结构
3. 更好的表格识别
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
    level: int = 1
    parent: Optional[str] = None


class EnhancedTextPreprocessor:
    """
    增强版文本预处理器
    
    改进点：
    1. 基于内容长度的智能章节边界检测
    2. 支持标准保险条款格式（如 2.6、2.6.1）
    3. 防止章节内容被截断
    """
    
    # 标准保险条款章节模式
    SECTION_PATTERNS = [
        # 一级标题：2. 保险责任 或 第2章 保险责任
        (r'^\s*(?:第)?(\d+)[章\s]+([\u4e00-\u9fa5]+(?:条款|责任|范围))\s*$', 1),
        # 二级标题：2.6 保险责任 或 2.6.1 住院医疗
        (r'^\s*(\d+)\.(\d+)(?:\.(\d+))?\s*([\u4e00-\u9fa5]+)\s*$', 2),
        # 带符号的标题
        (r'^\s*[【\[]([^【\]]{2,20})[】\]]\s*$', 1),
    ]
    
    # 关键章节关键词（用于模糊匹配和验证）
    KEY_SECTIONS = {
        '投保规则': ['投保年龄', '投保范围', '犹豫期'],
        '保险责任': ['保险责任', '保障范围', '我们保什么', '给付条件'],
        '免赔额': ['免赔额', ' deductible'],
        '赔付比例': ['给付比例', '赔付比例', '报销比例'],
        '续保条款': ['续保', '保证续保', '续保期间'],
        '医疗机构': ['医院', '医疗机构', '就诊医院', '医院范围'],
        '责任免除': ['责任免除', '免责', '我们不承担'],
        '等待期': ['等待期', '观察期'],
        '保险金申请': ['保险金申请', '理赔', '如何申请'],
    }
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.reader = PdfReader(pdf_path)
        self.pages_text = []
        self.full_text = ""
        
    def preprocess(self) -> Dict[str, Section]:
        """执行完整的预处理流程"""
        # Step 1: 提取所有页面文本
        self._extract_all_pages()
        
        # Step 2: 智能章节切分
        sections = self._smart_split_sections()
        
        return sections
    
    def _extract_all_pages(self):
        """提取所有页面的文本"""
        for i, page in enumerate(self.reader.pages, 1):
            text = page.extract_text() or ""
            self.pages_text.append({
                'page_num': i,
                'text': text
            })
        
        # 合并完整文本
        self.full_text = "\n".join([p['text'] for p in self.pages_text])
    
    def _smart_split_sections(self) -> Dict[str, Section]:
        """
        智能章节切分
        
        策略：
        1. 识别所有潜在的章节标题及其位置
        2. 根据标题层级和内容长度确定边界
        3. 确保章节内容完整性
        """
        sections = {}
        lines = self.full_text.split('\n')
        
        # 查找所有标题位置
        headings = self._find_all_headings(lines)
        
        if not headings:
            # 如果没有找到标题，尝试关键词分割
            return self._split_by_keywords(lines)
        
        # 根据标题划分章节
        for i, heading in enumerate(headings):
            title = heading['title']
            start_line = heading['line_num']
            start_page = self._get_page_for_line(start_line, lines)
            
            # 确定结束位置
            if i < len(headings) - 1:
                end_line = headings[i + 1]['line_num']
                end_page = self._get_page_for_line(end_line, lines)
            else:
                end_line = len(lines)
                end_page = len(self.reader.pages)
            
            # 提取章节文本（包含更多上下文）
            section_lines = lines[start_line:end_line]
            section_text = '\n'.join(section_lines).strip()
            
            # 标准化标题
            normalized_title = self._normalize_section_title(title)
            
            # 只保留有实质内容的章节（至少100字符）
            if len(section_text) >= 100:
                sections[normalized_title] = Section(
                    title=title,
                    start_page=start_page,
                    end_page=end_page,
                    text=section_text,
                    level=heading['level']
                )
        
        return sections
    
    def _find_all_headings(self, lines: List[str]) -> List[Dict]:
        """查找所有章节标题"""
        headings = []
        
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # 尝试匹配各种标题模式
            for pattern, level in self.SECTION_PATTERNS:
                match = re.match(pattern, line_stripped)
                if match:
                    # 提取标题文本
                    if len(match.groups()) >= 2:
                        # 对于带数字的模式，取最后一个组作为标题
                        title = match.groups()[-1]
                    else:
                        title = match.group(1)
                    
                    headings.append({
                        'title': title,
                        'line_num': line_num,
                        'level': level,
                        'raw_line': line_stripped
                    })
                    break
        
        # 按行号排序
        headings.sort(key=lambda x: x['line_num'])
        
        return headings
    
    def _split_by_keywords(self, lines: List[str]) -> Dict[str, Section]:
        """通过关键词分割章节（备用方案）"""
        sections = {}
        
        for standard_name, keywords in self.KEY_SECTIONS.items():
            best_match = None
            best_score = 0
            
            for line_num, line in enumerate(lines):
                line_lower = line.lower()
                score = 0
                
                for keyword in keywords:
                    if keyword in line:
                        score += 1
                        # 如果这一行较短，更可能是标题
                        if len(line.strip()) < 30:
                            score += 2
                
                if score > best_score:
                    best_score = score
                    best_match = line_num
            
            if best_match and best_score >= 2:
                # 找到该章节的内容范围
                start_line = best_match
                
                # 查找下一个章节或文档结尾
                end_line = len(lines)
                for other_name, other_keywords in self.KEY_SECTIONS.items():
                    if other_name == standard_name:
                        continue
                    for line_num in range(start_line + 1, min(start_line + 200, len(lines))):
                        for keyword in other_keywords:
                            if keyword in lines[line_num] and len(lines[line_num].strip()) < 30:
                                if line_num < end_line:
                                    end_line = line_num
                                    break
                
                section_text = '\n'.join(lines[start_line:end_line]).strip()
                
                if len(section_text) >= 50:
                    sections[standard_name] = Section(
                        title=standard_name,
                        start_page=self._get_page_for_line(start_line, lines),
                        end_page=self._get_page_for_line(end_line, lines),
                        text=section_text,
                        level=1
                    )
        
        return sections
    
    def _get_page_for_line(self, line_num: int, lines: List[str]) -> int:
        """根据行号估算页码"""
        total_lines = len(lines)
        total_pages = len(self.reader.pages)
        
        if total_lines == 0:
            return 1
        
        # 简单按比例估算
        estimated_page = int((line_num / total_lines) * total_pages) + 1
        return min(estimated_page, total_pages)
    
    def _normalize_section_title(self, title: str) -> str:
        """标准化章节标题"""
        title_clean = title.strip()
        
        for standard_name, keywords in self.KEY_SECTIONS.items():
            for keyword in keywords:
                if keyword in title_clean:
                    return standard_name
        
        return title_clean
    
    def get_section_text(self, section_name: str) -> Optional[str]:
        """获取指定章节的文本"""
        sections = self.preprocess()
        
        # 直接匹配
        if section_name in sections:
            return sections[section_name].text
        
        # 模糊匹配
        for key, section in sections.items():
            if section_name in key or key in section_name:
                return section.text
        
        return None


def enhanced_preprocess_pdf(pdf_path: str) -> Dict:
    """便捷的PDF预处理函数"""
    preprocessor = EnhancedTextPreprocessor(pdf_path)
    sections = preprocessor.preprocess()
    
    return {
        'sections': {
            name: {
                'title': section.title,
                'start_page': section.start_page,
                'end_page': section.end_page,
                'text': section.text[:1500] + '...' if len(section.text) > 1500 else section.text,
                'level': section.level,
                'text_length': len(section.text)
            }
            for name, section in sections.items()
        },
        'statistics': {
            'total_sections': len(sections),
            'total_pages': len(preprocessor.reader.pages),
            'total_chars': len(preprocessor.full_text)
        }
    }


if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("用法: python layer1_enhanced.py <pdf文件> [输出json文件]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "enhanced_preprocessing.json"
    
    result = enhanced_preprocess_pdf(pdf_path)
    
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 增强预处理完成！")
    print(f"📄 发现 {result['statistics']['total_sections']} 个章节")
    print(f"💾 结果已保存: {output}")
