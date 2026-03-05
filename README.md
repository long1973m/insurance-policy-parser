# 保险条款结构化解析技能

## 版本
Stage3-v3.0 (完整版)

## 架构概述

三层式架构设计：

```
┌─────────────────────────────────────────┐
│  Layer 1: 文本预处理                      │
│  - PDF转文本                              │
│  - 智能章节切分                            │
│  - 表格识别                               │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│  Layer 2: 三技能并行字段抽取               │
│                                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ Skill 1 │ │ Skill 2 │ │ Skill 3 │  │
│  │ 数值型  │ │ 逻辑型  │ │ 场景型  │  │
│  │ 6字段   │ │ 4字段   │ │ 6字段   │  │
│  └─────────┘ └─────────┘ └─────────┘  │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│  Layer 3: 冲突与质量控制                  │
│  - 逻辑冲突检测                           │
│  - 质量评分 (0-1)                        │
│  - needs_review标记                      │
│  - 审核建议生成                           │
└─────────────────────────────────────────┘
```

## 文件说明

### 核心组件

| 文件 | 层级 | 功能 | 抽取字段数 |
|------|------|------|-----------|
| `layer1_enhanced.py` | Layer 1 | 增强版章节切分 | - |
| `layer2_skill1_numeric_extractor.py` | Layer 2-Skill 1 | 数值型字段抽取 | 6个 |
| `layer2_skill2_logic_extractor.py` | Layer 2-Skill 2 | 逻辑类字段抽取 | 4个 |
| `layer2_skill3_contextual_extractor.py` | Layer 2-Skill 3 | 场景类字段抽取 | 6个 |
| `layer3_quality_controller.py` | Layer 3 | 质量控制 | - |
| `table_extractor.py` | 辅助 | 表格数据抽取 | - |

### 流水线脚本

| 文件 | 说明 |
|------|------|
| `pipeline_stage3.py` | **推荐使用** - 阶段三完整流水线 |
| `pipeline_stage2.py` | 阶段二流水线（无场景类字段） |
| `pipeline_mvp.py` | MVP版本（仅数值型字段） |

### 历史版本

| 文件 | 说明 |
|------|------|
| `extract_insurance.py` | V1.0 - 基础版本 |
| `extract_insurance_v2.py` | V2.0 - Markdown输出 |
| `extract_insurance_v3.py` | V3.0 - JSON+source_text |

### 文档

| 文件 | 说明 |
|------|------|
| `SKILL.md` | 技能使用文档 |
| `README.md` | 本文件 |

## 使用方法

### 推荐用法（阶段三完整版）

```bash
python pipeline_stage3.py <pdf文件> [输出json文件]
```

示例：
```bash
python pipeline_stage3.py policy.pdf result.json
```

### Python调用

```python
from pipeline_stage3 import run_stage3_pipeline

result = run_stage3_pipeline("policy.pdf", "output.json")
```

## 抽取字段清单

### Level 1: 绝对核心字段（6个）
- `total_annual_limit` - 年度总限额
- `deductible_amount` - 免赔额金额
- `deductible_unit` - 免赔额单位
- `reimbursement_ratio_with_social_security` - 有社保赔付比例
- `reimbursement_ratio_without_social_security` - 无社保赔付比例
- `waiting_period_days` - 等待期天数

### Level 2: 续保与逻辑字段（4个）
- `renewal_guaranteed` - 是否保证续保
- `renewal_guarantee_years` - 保证续保年限
- `renewal_requires_health_recheck` - 续保是否需重新健康告知
- `premium_adjustment_cap` - 费率调整上限

### Level 3: 场景限制字段（6个）
- `hospital_level_requirement` - 医院等级要求
- `public_hospital_required` - 是否仅限公立医院
- `emergency_hospital_exception` - 紧急情况医院例外
- `overseas_treatment_covered` - 海外就医
- `green_channel_covered` - 绿色通道
- `claim_direct_billing_available` - 直付服务

## 输出格式

```json
{
  "pipeline_version": "Stage3-v3.0",
  "layer1_preprocessing": {...},
  "layer2_extraction": {
    "fields": {
      "field_name": {
        "value": ...,
        "source_text": "...",
        "confidence": 0.90,
        "skill": "numeric|logic|contextual"
      }
    }
  },
  "layer3_quality": {
    "quality_score": 0.85,
    "needs_review": false,
    "conflicts": [...]
  }
}
```

## 特性亮点

1. **source_text可追溯** - 每个字段都有原始文本来源
2. **置信度评分** - 评估抽取结果的可靠性
3. **语境识别** - 区分一般情况 vs 紧急情况
4. **否定优先原则** - "不保证续保" > "保证续保"
5. **质量评分** - 自动生成0-1分的质量评分

## 已测试产品

- ✅ 君龙人寿 - 君龙君医保百万医疗险
- ✅ 众安保险 - 众民保2025
- ✅ 人保财险 - 长相安3号庆典版

## 下一步优化方向

1. 优化赔付比例从表格中的抽取
2. 添加更多保险公司条款格式支持
3. 引入轻量级NLP进行语境理解
4. 建立反馈学习机制

---

*创建时间：2026-03-04*
*版本：Stage3-v3.0*
