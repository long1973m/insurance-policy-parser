#!/usr/bin/env python3
"""
Layer 1 增强版 v2：针对众安保险优化的文本预处理
主要改进：
1. 支持众安保险的章节格式（一）（二）（三）
2. 添加更多关键词变体
3. PDF 质量检查
4. 表格区域识别
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

try:
    from PyPDF2 import PdfReader
    import fitz  # PyMuPDF for better text extraction
except ImportError as e:
    raise ImportError(f"缺少依赖：{e}\n请安装：pip install PyPDF2 pymupdf")


@dataclass
class Section:
    """章节数据结构"""
    title: str
    start_page: int
    end_page: int
    text: str
    level: int = 1
    parent: Optional[str] = None
    section_type: str = "normal"  # normal, table, definition


@dataclass
class PreprocessingResult:
    """预处理结果"""
    total_pages: int
    total_chars: int
    total_sections: int
    is_text_pdf: bool
    quality_score: float
    sections: List[Section]
    tables_detected: List[Dict]
    warnings: List[str]


class EnhancedTextPreprocessor:
    """增强版文本预处理器"""
    
    # 章节标题模式（支持多种格式）
    SECTION_PATTERNS = [
        # 众安格式：（一）（二）（三）
        (r'[（(]([一二三四五六七八九十百零\d]+)[)）]\s*([^\n]{1,50})', 2),
        # 传统格式：第一条、第二部分
        (r'第 ([一二三四五六七八九十百零\d]+) [条部分章节]', 1),
        # 人保健康数字格式：3.1、3.2（带小数点）
        (r'^(\d+\.\d+)\s+([^\n]{1,50})', 1),
        # 数字格式：1. 2. 3.
        (r'^(\d+)\.\s+([A-Z][^\n]{0,50})', 1),
        # 带括号数字：(1) (2)
        (r'[（(](\d+)[)）]\s*([^\n]{1,50})', 2),
    ]
    
    # 关键字段关键词变体
    KEYWORD_VARIANTS = {
        'deductible': [
            '免赔额', '免赔', '个人先承担', '自行承担', '个人自负',
            '个人支付', '先行承担', '扣除免赔', '约定的免赔'
        ],
        'waiting_period': [
            '等待期', '观察期', '等候期', '等待期间'
        ],
        'reimbursement_ratio': [
            '赔付比例', '给付比例', '报销比例', '赔付', '给付',
            '按比例', '100%', '80%', '60%'
        ],
        'renewal': [
            '续保', '保证续保', '不保证续保', '续保申请', '重新投保'
        ],
        'hospital_level': [
            '医院等级', '二级及以上', '三级医院', '公立医院',
            '卫生行政部门'
        ],
        'overseas': [
            '海外', '境外', '国外', '香港', '澳门', '台湾',
            '中国大陆以外'
        ]
    }
    
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.warnings = []
        
    def check_pdf_quality(self) -> Tuple[bool, float, str]:
        """
        检查 PDF 质量
        返回：(is_text_pdf, quality_score, message)
        """
        if not self.pdf_path.exists():
            return False, 0.0, f"文件不存在：{self.pdf_path}"
        
        try:
            doc = fitz.open(str(self.pdf_path))
        except Exception as e:
            return False, 0.0, f"无法打开 PDF: {e}"
        
        total_pages = len(doc)
        if total_pages == 0:
            return False, 0.0, "PDF 为空"
        
        # 检查前 5 页
        total_chars = 0
        total_images = 0
        text_pages = 0
        
        for i in range(min(5, total_pages)):
            page = doc[i]
            text = page.get_text()
            images = page.get_images()
            
            char_count = len(text.strip())
            total_chars += char_count
            total_images += len(images)
            
            if char_count > 100:
                text_pages += 1
        
        doc.close()
        
        # 判断是否是文字型 PDF
        is_text_pdf = text_pages >= 3  # 至少 3 页有文字
        
        # 计算质量评分
        avg_chars_per_page = total_chars / min(5, total_pages)
        
        if is_text_pdf:
            if avg_chars_per_page > 500:
                quality_score = 0.9
                message = "文字型 PDF，质量良好"
            elif avg_chars_per_page > 200:
                quality_score = 0.7
                message = "文字型 PDF，但文字较少"
            else:
                quality_score = 0.5
                message = "文字型 PDF，但文字很少，可能是扫描件"
        else:
            quality_score = 0.2
            message = "可能是扫描件或图片型 PDF，文字提取困难"
        
        # 添加警告
        if total_images > 10:
            self.warnings.append(f"PDF 包含大量图片 ({total_images}个)，可能影响提取")
        
        if text_pages < 3:
            self.warnings.append("前 5 页中只有少数页面包含文字，建议检查 PDF 质量")
        
        return is_text_pdf, quality_score, message
    
    def detect_section_type(self, text: str) -> str:
        """检测章节类型"""
        # 检查是否包含表格特征
        table_indicators = ['|', '┌', '─', '┐', '│', '└', '┘', '├', '┤']
        if any(ind in text for ind in table_indicators):
            return "table"
        
        # 检查是否是释义/定义
        definition_patterns = [r'释义 \d+', r'\(释义 [一二三四五六七八九十零\d]+\)', r'是指', '系指']
        if any(re.search(p, text) for p in definition_patterns):
            return "definition"
        
        return "normal"
    
    def extract_sections(self, text: str, total_pages: int) -> List[Section]:
        """
        智能章节切分
        支持多种格式识别
        """
        sections = []
        
        # 尝试每种章节模式
        for pattern_idx, (pattern, group_idx) in enumerate(self.SECTION_PATTERNS):
            matches = list(re.finditer(pattern, text, re.MULTILINE))
            
            if len(matches) < 2:
                continue  # 这个模式不适用，试下一个
            
            # 找到所有章节起始位置
            section_starts = []
            for match in matches:
                start_pos = match.start()
                
                # 提取章节标题
                if group_idx == 1:
                    title = match.group(0)
                else:
                    title = f"({match.group(1)}) {match.group(2)}" if match.group(2) else f"({match.group(1)})"
                
                # 估算页码（简单按字符比例）
                estimated_page = int((start_pos / len(text)) * total_pages) + 1
                
                section_starts.append({
                    'pos': start_pos,
                    'title': title,
                    'page': estimated_page,
                    'level': 1 if pattern_idx == 0 else 2
                })
            
            # 创建章节对象
            for i, start in enumerate(section_starts):
                end_pos = section_starts[i + 1]['pos'] if i + 1 < len(section_starts) else len(text)
                section_text = text[start['pos']:end_pos].strip()
                
                # 检测章节类型
                section_type = self.detect_section_type(section_text)
                
                section = Section(
                    title=start['title'],
                    start_page=start['page'],
                    end_page=section_starts[i + 1]['page'] if i + 1 < len(section_starts) else total_pages,
                    text=section_text,  # 保存完整文本
                    level=start['level'],
                    section_type=section_type
                )
                sections.append(section)
            
            # 如果找到章节就停止（优先使用最匹配的模式）
            if len(sections) >= 3:
                break
        
        # 如果还是没找到章节，按大段落切分
        if len(sections) == 0:
            self.warnings.append("未识别到标准章节格式，按段落切分")
            paragraphs = re.split(r'\n\s*\n', text)
            
            current_page = 1
            for i, para in enumerate(paragraphs):
                if len(para.strip()) > 200:  # 只保留较长的段落
                    section = Section(
                        title=f"段落 {i+1}",
                        start_page=current_page,
                        end_page=current_page,
                        text=para.strip()[:500],
                        level=3,
                        section_type="normal"
                    )
                    sections.append(section)
                    
                    # 每 5 个段落算一页（粗略估计）
                    if i % 5 == 0:
                        current_page += 1
        
        return sections
    
    def detect_tables(self, text: str) -> List[Dict]:
        """检测表格区域"""
        tables = []
        
        # 简单表格检测（基于字符模式）
        table_patterns = [
            r'[│┃].*[│┃]',  # 竖线表格
            r'[─━═].*[─━═]',  # 横线表格
            r'\|.*\|.*\|',  # Markdown 表格
        ]
        
        for pattern in table_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                table_context = text[start:end]
                
                tables.append({
                    'position': match.start(),
                    'preview': table_context[:200],
                    'pattern': pattern
                })
        
        return tables
    
    def preprocess(self) -> PreprocessingResult:
        """执行预处理"""
        # 1. PDF 质量检查
        is_text_pdf, quality_score, quality_msg = self.check_pdf_quality()
        
        print(f"📄 PDF 质量检查：{quality_msg}")
        print(f"   质量评分：{quality_score:.2f}")
        
        if not is_text_pdf:
            self.warnings.append("PDF 可能不是文字型，提取结果可能不准确")
        
        # 2. 提取文本
        try:
            reader = PdfReader(str(self.pdf_path))
            total_pages = len(reader.pages)
            
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() or ""
            
            total_chars = len(full_text)
            
        except Exception as e:
            # 回退到 PyMuPDF
            try:
                doc = fitz.open(str(self.pdf_path))
                total_pages = len(doc)
                full_text = ""
                for page in doc:
                    full_text += page.get_text()
                doc.close()
                total_chars = len(full_text)
            except Exception as e2:
                return PreprocessingResult(
                    total_pages=0,
                    total_chars=0,
                    total_sections=0,
                    is_text_pdf=False,
                    quality_score=0.0,
                    sections=[],
                    tables_detected=[],
                    warnings=[f"无法提取文本：{e}", f"回退失败：{e2}"]
                )
        
        print(f"✅ 文本提取完成")
        print(f"   总页数：{total_pages}")
        print(f"   总字符数：{total_chars:,}")
        
        # 3. 章节切分
        sections = self.extract_sections(full_text, total_pages)
        print(f"✅ 章节识别完成：{len(sections)}个")
        
        # 4. 表格检测
        tables = self.detect_tables(full_text)
        if tables:
            print(f"⚠️ 检测到 {len(tables)} 个表格区域")
        
        # 5. 打印警告
        if self.warnings:
            print(f"\n⚠️ 警告 ({len(self.warnings)}条):")
            for w in self.warnings[:5]:
                print(f"   - {w}")
        
        return PreprocessingResult(
            total_pages=total_pages,
            total_chars=total_chars,
            total_sections=len(sections),
            is_text_pdf=is_text_pdf,
            quality_score=quality_score,
            sections=sections,
            tables_detected=tables,
            warnings=self.warnings
        )


def run_layer1_preprocessing(pdf_path: str) -> Dict:
    """Layer 1 入口函数"""
    print("\n📦 Layer 1: 增强文本预处理 v2")
    print("-" * 40)
    
    processor = EnhancedTextPreprocessor(pdf_path)
    result = processor.preprocess()
    
    # 转换为字典格式（兼容原有 pipeline）
    return {
        'total_pages': result.total_pages,
        'total_chars': result.total_chars,
        'total_sections': result.total_sections,
        'is_text_pdf': result.is_text_pdf,
        'quality_score': result.quality_score,
        'sections': [asdict(s) for s in result.sections],
        'tables_detected': result.tables_detected,
        'warnings': result.warnings
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法：python layer1_enhanced_v2.py <pdf 文件> [输出 json]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = run_layer1_preprocessing(pdf_path)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 结果已保存：{output_path}")
    
    # 打印章节预览
    if result['sections']:
        print("\n📋 章节预览（前 5 个）:")
        for i, sec in enumerate(result['sections'][:5], 1):
            print(f"   {i}. {sec['title']} (第{sec['start_page']}-{sec['end_page']}页) [{sec['section_type']}]")
