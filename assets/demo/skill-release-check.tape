Output "skill-release-check-demo.gif"
Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 760
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
Type "cd /path/to/skill-release-check" Enter
Type "clear" Enter
Show
Sleep 600ms
Type "# 对着一个 skill 目录跑：结构 / 可移植性 / 隐私 / 许可证 一次过筛" Sleep 400ms Enter
Sleep 1s
Type "python3 scripts/check_skill_readiness.py . | head -14" Sleep 300ms Enter
Sleep 3500ms
Type "# 零依赖、不写盘、不联网 · 发布前一键过筛 ✅" Enter
Sleep 2800ms
