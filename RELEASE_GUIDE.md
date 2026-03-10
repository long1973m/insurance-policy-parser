# 📦 v2 发布指南

## 本次更新内容

### 核心改进
1. **增强章节识别** - 支持众安、人保健康等多种格式
2. **LLM 增强抽取** - 语义理解 + 规则匹配
3. **PDF 质量检查** - 提前识别扫描件
4. **智能报告** - 自然语言摘要 + 质量评分

### 新增文件
- `layer1_enhanced_v2.py`
- `layer2_llm_enhanced.py`
- `pipeline_v2_optimized.py`
- `OPTIMIZATION_LOG.md`
- `CHANGELOG.md`

### 更新文件
- `README.md` - 完整重写
- `SKILL.md` - 更新触发条件

---

## 🚀 Git 提交步骤

### 步骤 1：进入目录
```bash
cd /Users/mare/.copaw/active_skills/insurance-policy-compare
```

### 步骤 2：查看变更
```bash
git status
```

### 步骤 3：添加所有文件
```bash
git add .
```

### 步骤 4：提交
```bash
git commit -m "v2-optimized: 增强章节识别 + LLM 增强抽取

主要改进:
- Layer 1 v2: 支持多种章节格式（众安、人保健康等）
- Layer 2 LLM: 语义理解 + 规则匹配
- PDF 质量检查：识别文字型/扫描件
- 智能报告：自然语言摘要

效果:
- 章节识别：0 → 816 个
- 等待期抽取：准确率提升
- 关键洞察：识别条款 vs 保险单区别

新增文件:
- layer1_enhanced_v2.py
- layer2_llm_enhanced.py  
- pipeline_v2_optimized.py
- CHANGELOG.md

更新文件:
- README.md (完整重写)
- SKILL.md (更新触发条件)
"
```

### 步骤 5：推送到 GitHub
```bash
git push origin main
```

如果提示设置上游分支：
```bash
git push --set-upstream origin main
```

---

## 📋 ClawHub 发布

### 步骤 1：检查 SKILL.md
确认 `SKILL.md` 中的描述准确：
- ✅ name: insurance-policy-parser
- ✅ description: 包含触发条件
- ✅ 已更新支持的产品列表

### 步骤 2：发布到 ClawHub
参考 ClawHub 文档进行发布。

---

## ✅ 发布后检查

### 1. GitHub 仓库
- [ ] 代码已推送
- [ ] README 显示正常
- [ ] CHANGELOG 已更新

### 2. 功能测试
```bash
# 测试优化版流水线
python pipeline_v2_optimized.py /tmp/test_policy.pdf /tmp/result.json

# 查看结果
cat /tmp/result.json
```

### 3. 文档检查
- [ ] README.md 清晰
- [ ] CHANGELOG.md 完整
- [ ] SKILL.md 准确

---

## 🎉 发布完成！

发布后记得：
1. 在 GitHub 上创建 Release（可选）
2. 分享到社区（CSDN、鲸社区等）
3. 收集用户反馈
4. 持续迭代优化

---

*发布时间：2026-03-10*
*版本：v2-optimized*
