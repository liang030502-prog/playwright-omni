# 贡献指南 | Contributing Guide

## 分支策略 | Branch Strategy

```
main          ← 稳定版本，永远可部署
├── develop   ← 开发主线（可选）
├── feature/* ← 新功能开发
├── fix/*     ← Bug 修复
└── refactor/*← 重构
```

**重要**：禁止直接往 `main` 推送代码。所有改动必须通过 PR 合并。

---

## Commit 规范 | Commit Convention

每次提交必须遵循以下格式：

```
<类型>: <简短描述>

类型说明：
- feat    新功能
- fix     Bug 修复
- refactor 重构（不修 bug，也不加功能）
- docs    文档更新
- test    测试相关
- chore   工具/依赖/构建相关
```

**示例：**
```bash
git commit -m "feat: add self-healing dialog handler for CDP browser"
git commit -m "fix: resolve IndexError on browser restart"
git commit -m "docs: update SKILL.md with new trigger words"
```

**Commit 规则：**
- 用中文写描述，简洁明了，不超过 72 字
- 每个 commit 应该是**原子性的**（一件事，不是多件事）
- 先写测试再写代码（推荐 TDD 流程）

---

## Pull Request 流程 | PR Workflow

### 1. 创建分支
```bash
git checkout main
git pull
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/bug-description
```

### 2. 开发与提交
```bash
git add <改动的文件>
git commit -m "类型: 描述"
git push -u origin HEAD
```

### 3. 创建 PR
在 GitHub 上创建 Pull Request，描述：
- **解决了什么问题**
- **怎么测试的**
- **改动了什么**

### 4. Review 与合并
- 需要 1 个 approve 才能合并
- 合并后删除分支

---

## 测试规范 | Testing

所有新增代码**必须有测试**：

```bash
# 运行所有测试
pytest

# 运行特定模块测试
pytest tests/test_preflight.py -v

# 运行带覆盖率
pytest --cov=scripts --cov-report=html
```

**TDD 流程（推荐）：**
1. 先写测试（RED）
2. 写代码让测试通过（GREEN）
3. 重构代码（REFACTOR）
4. 提交

---

## 代码风格 | Code Style

- Python：遵循 PEP 8
- 使用 4 空格缩进
- 变量命名：英文，见名知意
- 每个函数要有 docstring

---

## 文件结构 | Project Structure

```
playwright-omni/
├── scripts/           ← 核心源代码
│   ├── preflight_check.py
│   ├── orchestrator.py
│   ├── vision_decision.py
│   └── ...
├── tests/            ← 测试代码
│   ├── test_preflight.py
│   └── ...
├── SKILL.md          ← Skill 元数据
├── CONTRIBUTING.md   ← 本文件
└── README.md         ← 项目说明
```

---

## 问题与讨论

如有疑问或发现文档过时的地方，请提 Issue 或 PR。