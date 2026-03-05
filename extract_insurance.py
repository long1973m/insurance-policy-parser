#!/usr/bin/env python3
"""
保险条款核心字段抽取与对比工具
用于从PDF格式的保险条款中抽取关键信息并生成对比表
"""

import os
import re
from pathlib import Path

try:
    from PyPDF2 import PdfReader
except ImportError:
    raise ImportError("请先安装 PyPDF2: pip install PyPDF2")


def extract_text_from_pdf(pdf_path):
    """从PDF文件中提取文本内容"""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def extract_core_fields(text):
    """从保险条款文本中抽取核心保障字段"""
    fields = {}

    # 产品名称
    name_match = re.search(r"(.*保险.*?条款)", text)
    fields["产品名称"] = name_match.group(1)[:40] if name_match else "未识别"

    # 年度免赔额
    deductible_match = re.search(r"免赔额[为：:]?([\d,]+元)", text)
    fields["年度免赔额"] = deductible_match.group(1) if deductible_match else "未识别"

    # 报销比例
    reimbursement_match = re.search(r"报销比例[为：:]?([\d]+%)", text)
    fields["报销比例"] = reimbursement_match.group(1) if reimbursement_match else "未识别"

    # 外购药
    if "外购药" in text:
        fields["是否包含外购药"] = "可能包含（需人工确认）"
    else:
        fields["是否包含外购药"] = "未识别"

    # 等待期
    waiting_match = re.search(r"等待期[为：:]?([\d]+天)", text)
    fields["等待期"] = waiting_match.group(1) if waiting_match else "未识别"

    # 保障责任概述
    coverage_match = re.search(r"保障责任(.{0,200})", text)
    fields["保障责任概述"] = coverage_match.group(1)[:150] if coverage_match else "未识别"

    return fields


def generate_markdown_comparison(fields1, fields2):
    """生成Markdown格式的对比表"""
    keys = fields1.keys()
    md = "# 保险条款对比表\n\n"
    md += "| 字段 | 产品A | 产品B |\n"
    md += "|------|--------|--------|\n"
    for key in keys:
        val1 = fields1[key].replace("|", "\\|")  # 转义表格中的管道符
        val2 = fields2[key].replace("|", "\\|")
        md += f"| {key} | {val1} | {val2} |\n"
    return md


def compare_policies(pdf_path_1, pdf_path_2, output_path="insurance_comparison.md"):
    """
    对比两个保险条款PDF文件

    Args:
        pdf_path_1: 第一个保险条款PDF文件路径
        pdf_path_2: 第二个保险条款PDF文件路径
        output_path: 输出Markdown文件路径，默认为 insurance_comparison.md

    Returns:
        str: 操作结果信息
    """
    # 验证文件存在
    if not Path(pdf_path_1).exists():
        return f"❌ 文件不存在: {pdf_path_1}"
    if not Path(pdf_path_2).exists():
        return f"❌ 文件不存在: {pdf_path_2}"

    try:
        # 提取文本
        text1 = extract_text_from_pdf(pdf_path_1)
        text2 = extract_text_from_pdf(pdf_path_2)

        # 抽取核心字段
        fields1 = extract_core_fields(text1)
        fields2 = extract_core_fields(text2)

        # 生成对比表
        md_content = generate_markdown_comparison(fields1, fields2)

        # 保存文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return f"✅ 对比完成，已生成文件: {output_path}"

    except Exception as e:
        return f"❌ 处理过程中出错: {str(e)}"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("用法: python extract_insurance.py <pdf文件1> <pdf文件2> [输出文件]")
        print("示例: python extract_insurance.py policy_a.pdf policy_b.pdf comparison.md")
        sys.exit(1)

    pdf1 = sys.argv[1]
    pdf2 = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) > 3 else "insurance_comparison.md"

    result = compare_policies(pdf1, pdf2, output)
    print(result)
