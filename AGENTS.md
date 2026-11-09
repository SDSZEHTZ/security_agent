# 项目协作说明

## Superpowers

本项目已安装 Superpowers，技能位于 `.agents/skills/`，仅作用于本仓库。

- 开始任务时，先阅读 `.agents/skills/using-superpowers/SKILL.md`，再按任务需要读取相关技能。
- 在 Codex 中同时参考 `.agents/skills/using-superpowers/references/codex-tools.md`；以当前实际可用工具和平台指令为准。
- 如果技能调用入口尚未刷新，直接读取对应的 `SKILL.md` 并遵循其工作流。
- 技能中 `superpowers:<name>` 对应本项目 `.agents/skills/<name>/SKILL.md`。
- 新功能按需使用 `brainstorming`、`writing-plans` 和 `test-driven-development`；排查故障使用 `systematic-debugging`。
- 宣告工作完成前使用 `verification-before-completion`，提供实际验证结果。
- 技能不能覆盖系统、开发者指令、用户明确要求及工具权限限制。

安装来源、固定版本及使用说明见 `docs/superpowers.md`。
