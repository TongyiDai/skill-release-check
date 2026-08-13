# Skill 开源就绪标准 (Skill Open-Source Readiness Standard)

这份标准回答一个问题：**一个 Agent Skill 要发布成公开开源、且对任意 agent 友好，必须满足什么？** 它把校验拆成四类，每类标出 `ERROR`（阻断发布）与 `WARNING`（应改、不阻断）。`scripts/check_skill_readiness.py` 是这份标准的可执行版本，二者必须保持一致。

标准依据：agentskills.io 开放标准、Anthropic《Skill authoring best practices》，以及一次真实审计中反复出现的开源事故（缺 LICENSE、真实姓名/内部术语泄露、硬编码 home 路径）。

## Contents

- [判定原则](#判定原则)
- [A. 结构与触发](#a-结构与触发)
- [B. 可移植性（跨 agent）](#b-可移植性跨-agent)
- [C. 健壮性](#c-健壮性)
- [D. 隐私与开源合规](#d-隐私与开源合规)
- [校验器与人工复核的边界](#校验器与人工复核的边界)

## 判定原则

- **ERROR 必须清零才能发布。** WARNING 应尽量清，但由人判断是否放行。
- **核心贴死开放标准，专属特性只做增强层。** 只用 `name`+`description`+markdown 正文 + `scripts/references/assets` 就能在 32+ 工具零改动运行；agent 专属字段（Codex 的 `agents/openai.yaml`、Claude 的 `when_to_use` 等）可共存，但核心功能不能依赖它们。
- **发布的是 git 内容。** 判断"能不能发"时用 `--tracked-only` 只看将被推送的文件；未跟踪的本地文件给 WARNING 而非 ERROR。
- **隐私检测只用通用启发式**（ID 格式、企业邮箱域、密钥模式），不维护具体人名黑名单——名单会漏、会过期，且名单本身就是敏感物。真实姓名类泄露最终靠人工复核兜底。

## A. 结构与触发

| 规则 | 级别 |
|---|---|
| skill 根目录存在 `SKILL.md` | ERROR |
| `SKILL.md` 有 YAML frontmatter | ERROR |
| frontmatter 含 `name` | ERROR |
| `name` 仅小写字母/数字/连字符，无首尾/连续连字符，≤64 字符 | ERROR |
| `name` 不含保留词（anthropic / claude） | ERROR |
| frontmatter 含 `description` 且 ≤1024 字符 | ERROR |
| `name` 与目录名一致 | WARNING |
| `description` 含"何时用/触发"表述 | WARNING |
| `description` 用第三人称（不写 "I/you can help…"） | WARNING |
| `SKILL.md` 正文 ≤500 行 | WARNING |
| skill 子目录内不放 `README.md`（单 skill 仓库根 README 例外） | WARNING |

`description` 是唯一的触发开关，也是唯一常驻上下文的字段：必须同时说清**做什么 + 何时用**，塞进真实触发词（含中文）。

## B. 可移植性（跨 agent）

| 规则 | 级别 |
|---|---|
| 无硬编码 per-user 绝对路径（`/Users/x`、`/home/x`、`C:\Users\`） | ERROR |
| 脚本无 Windows 反斜杠路径分隔 | WARNING |
| `references/` 引用一层深（不 A→B→C 嵌套） | WARNING |

路径一律相对 + 正斜杠；需要指向 home/agent 目录时用环境变量兜底（如 `${TRAE_HOME:-$HOME/.trae}`），不写死某台机器的路径。

## C. 健壮性

| 规则 | 级别 |
|---|---|
| markdown 无时效性措辞（示例：`XXXX 年 X 月前用旧 API` 这类会过期的表述） | WARNING |

补充（校验器不强制、评审应关注）：外部依赖（CLI、python/node 包）应显式声明而非假设已装；脚本自己处理错误、无魔法常数；关键/批量操作有校验或反馈闭环。

## D. 隐私与开源合规

| 规则 | 级别 |
|---|---|
| 无密钥模式（私钥、GitHub/OpenAI/AWS/Slack/Google token、Bearer） | ERROR |
| 无内部标识符（`ou_`/`oc_`/`cli_`/`on_` ID、Base token、企业邮箱域） | ERROR |
| skill 根目录有 `LICENSE` 文件 | ERROR |

人工复核必查（校验器无法可靠识别）：真实同事/客户姓名、内部工具与方法论代号、内部文档标题、真实业务数据。示例与 fixture 一律用合成/脱敏内容。

## 校验器与人工复核的边界

校验器抓的是**机械可判定**的问题，是早期预警，不是终审。以下必须人工复核：

- 真实人名、内部代号、真实业务数据（启发式抓不全）；
- `description` 是否真的能在对的时刻触发（建议 20 条查询测试：10 条应触发、10 条不应触发）；
- 画板/示例的语义正确性；
- LICENSE 类型是否合适（solo/开源默认 MIT；改编上游按上游许可，如 Apache-2.0 并保留 NOTICE）。
