---
name: skill-release-check
description: "检查一个 Agent Skill 是否达到开源发布标准：SKILL.md frontmatter 是否合法可触发、是否跨 agent 可移植（无硬编码 home 路径）、是否健壮，以及隐私与开源合规（无密钥、无内部标识符、有 LICENSE）。当用户要发布/开源 skill、创建 skill 后想自检、检查 skill 是否对任意 agent 友好、审计 skill 是否可安全公开，或说“skill 就绪检查”“skill 发布前检查”“check skill readiness”时使用。也作为 push-to-github 发布 skill 前的强制门。"
license: MIT
metadata:
  version: "1.0"
---

# Skill 开源就绪检查

在把一个 Agent Skill 公开发布前，用一套可执行标准判断它是否合格：能被正确触发、跨 agent 可移植、健壮、且不泄露隐私或缺失许可证。

标准的完整定义在 [references/standard.md](references/standard.md)，其可执行版本是 `scripts/check_skill_readiness.py`。二者是同一套规则的两种表述。

## 何时用

- 用户要发布 / 开源一个 skill 到 GitHub。
- 刚创建完 skill，想在发布前自检。
- 想确认某个 skill 对任意 agent（Codex / Claude Code / Cursor / TRAE 等）都友好。
- `push-to-github` 在发布 skill 类仓库前，把本检查作为强制门。

## 快速开始

从任意位置对一个 skill 目录运行校验器（纯 Python 3.8+ stdlib，无需安装依赖）：

```bash
python3 scripts/check_skill_readiness.py <skill-dir>
```

判断"能否发布"时，只看将被推送的 git 内容（推荐用于发布门）：

```bash
python3 scripts/check_skill_readiness.py <skill-dir> --tracked-only --json
```

- 退出码 `0` = 无 ERROR（可发布）；`1` = 有 ERROR（阻断）。
- `--json` 输出机器可读报告（`ok` / `errors` / `warnings` / `checks`）。
- `--strict` 把 WARNING 也视为失败。

## 校验器覆盖什么

四类检查，ERROR 阻断发布，WARNING 应改不阻断（完整清单见 standard.md）：

- **A 结构与触发**：SKILL.md 存在、frontmatter 合法、`name` 命名规则与目录一致、`description` 含触发词且第三人称、正文 ≤500 行。
- **B 可移植性**：无硬编码 `/Users/x`、`/home/x`、`C:\Users\` 等 per-user 路径；无 Windows 反斜杠路径；引用一层深。
- **C 健壮性**：无时效性措辞。
- **D 隐私与合规**：无密钥模式、无内部标识符（`ou_`/`cli_` 等 ID、企业邮箱域）、有 LICENSE。

## 校验器抓不到、必须人工复核的

校验器是早期预警，不是终审。以下靠人：

- **真实姓名、内部工具/方法论代号、真实业务数据**——用通用启发式无法可靠识别，发布前必须人工过一遍示例与 references。
- `description` 是否真能在对的场景触发（建议 20 条查询测试：10 应触发 / 10 不应）。
- LICENSE 类型是否合适（solo/开源默认 MIT；改编上游按上游许可并保留 NOTICE）。
- 画板 / 示例的语义正确性。

## 工作流

1. 对目标 skill 运行 `check_skill_readiness.py --tracked-only --json`。
2. 有 ERROR 先修到清零：补 LICENSE、去硬编码路径、移除密钥/内部 ID、修 frontmatter。
3. WARNING 逐条判断是否修（触发词、name 与目录一致、正文过长拆分等）。
4. 人工复核上一节列出的项，重点是真实姓名 / 内部术语 / 真实数据。
5. 通过后再进入发布流程（见 push-to-github）。
