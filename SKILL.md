---
name: insurance-policy-compare
description: Use when comparing two insurance policy PDF documents, extracting coverage details and generating comparison reports
---

# Insurance Policy Compare

## Overview

Extract core coverage fields from insurance policy PDFs and generate structured comparison reports. Supports standardized field extraction based on professional insurance analysis framework.

## When to Use

- Comparing two insurance products (e.g., medical, life, property)
- Extracting key terms like deductibles, reimbursement rates, waiting periods
- Creating structured comparison reports from unstructured policy documents
- Analyzing coverage differences between policy versions or competitors

**Input:** One or two PDF file paths containing insurance policy terms  
**Output:** JSON format with field values and source text references

## Field Extraction Framework

### Level 1: Core Fields (16 fields)
Absolute essential parameters that every medical insurance policy must specify:

| Category | Fields |
|----------|--------|
| **Coverage Limits** | total_annual_limit, deductible_amount, deductible_unit |
| **Reimbursement** | reimbursement_ratio_with_social_security, reimbursement_ratio_without_social_security |
| **Renewal Terms** | renewal_guaranteed, renewal_requires_health_recheck, renewal_guarantee_years, premium_adjustment_cap |
| **Hospital Requirements** | hospital_level_requirement, public_hospital_required |
| **Basic Coverage** | waiting_period_days, inpatient_medical_covered, drug_coverage_scope |
| **Advanced Treatments** | out_of_hospital_drug_covered, proton_heavy_ion_covered |

### Level 2: Enhancement Fields (16 fields)
Differentiating features that may vary across products:

| Category | Fields |
|----------|--------|
| **Family Features** | deductible_family_shared, social_security_offset_allowed, family_plan_available |
| **Outpatient Care** | special_outpatient_covered, outpatient_surgery_covered, pre_post_hospital_outpatient_days |
| **Critical Illness** | critical_disease_deductible_zero, critical_disease_separate_limit |
| **Drug Coverage** | targeted_drug_covered, car_t_covered, designated_drug_list_required |
| **Value-added Services** | green_channel_covered, claim_direct_billing_available |
| **Special Cases** | emergency_hospital_exception, overseas_treatment_covered, post_stop_transfer_right |

## Usage

### V3: JSON Output with Source Text (Recommended)
```python
from extract_insurance_v3 import extract_policy_to_json, extract_policy_to_dict

# Get JSON string with value and source_text for each field
json_result = extract_policy_to_json("/path/to/policy.pdf", indent=2)
print(json_result)

# Or get as Python dict
data = extract_policy_to_dict("/path/to/policy.pdf")
print(data["deductible_amount"]["value"])  # 10000.0
print(data["deductible_amount"]["source_text"])  # "免赔额余额为 基本医疗保险 范围内 10000元"
```

### Output Format
```json
{
  "deductible_amount": {
    "value": 10000.0,
    "source_text": "免赔额余额为 基本医疗保险 范围内 10000元"
  },
  "reimbursement_ratio_with_social_security": {
    "value": 1.0,
    "source_text": "保障计划载明的赔付比例的 100%"
  },
  "waiting_period_days": {
    "value": 90,
    "source_text": "90天内为等待期"
  }
}
```

### Two-Policy Comparison
```python
from extract_insurance_v3 import run

# Compare two policies - outputs JSON
result = run("/path/to/policy_a.pdf", "/path/to/policy_b.pdf", "comparison.json")
print(result)  # "分析完成，已生成JSON文件: comparison.json"
```

### Command Line
```bash
# Analyze single policy
python extract_insurance_v3.py policy.pdf output.json
```

## Implementation Details

The extraction uses multi-layer regex patterns optimized for Chinese insurance documents:

### Data Types Supported
- **DECIMAL(15,2)**: Monetary amounts (e.g., 1000000.00 for 1 million)
- **DECIMAL(5,4)**: Percentage ratios (e.g., 1.0000 for 100%)
- **BOOLEAN**: True/False flags
- **INT**: Integer values (days, years)
- **ENUM**: Categorical values with predefined options

### Source Text Tracking
Every extracted field includes the original text snippet for verification:
- Enables human review of AI extraction accuracy
- Provides traceability for compliance purposes
- Supports debugging and pattern refinement

### Example Patterns
- **Annual Limit**: `年度.*?(?:限额|保额).*?(\d{1,3}(?:,\d{3})*)\s*万`
- **Deductible**: `免赔额[为：:]?(\d{1,3}(?:,\d{3})*)\s*元`
- **Waiting Period**: `等待期[为：:]?(\d+)\s*天`
- **Renewal Years**: `保证续保\s*(\d+)\s*年`

## Version History

- **v1.0**: Basic field extraction (6 fields), Markdown output
- **v2.0**: Comprehensive framework with 32 standardized fields (Level 1 + Level 2), Markdown output
- **v3.0**: JSON output with source_text for every field, enhanced traceability and verifiability

## File Structure

```
insurance-policy-compare/
├── SKILL.md                    # This documentation
├── extract_insurance.py        # V1.0 - Basic version
├── extract_insurance_v2.py     # V2.0 - Full field set, Markdown output
└── extract_insurance_v3.py     # V3.0 - JSON output with source_text (recommended)
```

## Limitations & Notes

- Requires clean, text-based PDFs (not scanned images)
- Pattern matching may need adjustment for non-standard document formats
- Complex tables and nested structures may not extract perfectly
- Always verify critical numbers against original documents
- Some fields may return `null` if not explicitly stated in the policy
- Source text provides context but may include surrounding formatting characters
