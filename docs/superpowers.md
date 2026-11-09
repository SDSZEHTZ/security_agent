# Superpowers 项目级安装

- 来源：https://github.com/obra/superpowers
- 版本：7.0.2
- 固定提交：`22f0b463e7a5e579904dd6211a520321035526f7`
- 安装日期：2026-11-09
- 位置：`E:\security_agent\.agents\skills`
- 范围：当前仓库的 Codex 技能与协作流程。
- 许可证：MIT，见 `superpowers-LICENSE.txt`。

使用 Codex 自带 `skill-installer` 的 `install-skill-from-github.py`，通过
`--repo obra/superpowers --ref <固定提交> --dest E:\security_agent\.agents\skills`
安装上游 `skills/` 下全部 15 项技能及各自配套资源。
`superpowers-install.json` 记录技能清单及文件 SHA-256 校验值。

## 使用

根目录 `AGENTS.md` 指定了 Superpowers 的入口。后续任务根据实际需要读取相应技能。
例如，可要求“使用 systematic-debugging 排查测试失败”，或“使用 brainstorming 设计新功能”。

Codex 会自动发现 `.agents/skills` 中的项目技能。安装后下一轮即可使用；
如果技能列表未刷新，重新启动 Codex 后在本项目继续。
加载规则参考：https://learn.chatgpt.com/docs/build-skills

这是项目级技能安装，未注册应用级市场插件或会话钩子。
当前会话已具备多代理工具；其他环境的工具是否可用，以其实际配置为准。
上游附带的 Shell、Node 或 Python 辅助脚本只在对应工作流需要时运行，
本次安装只校验文件，没有执行这些辅助脚本。

## 更新

更新时先核实上游提交和变更记录，备份本地定制，再使用安装器安装到独立临时目录，
检查差异后替换本项目的对应技能，同时更新版本、许可证和校验清单。
安装器不会覆盖已存在的同名技能目录。
