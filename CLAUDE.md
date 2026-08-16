# CLAUDE.md

本文件为 Claude Code 专用约定，与 `AGENTS.md` 内容保持一致；详见 [`AGENTS.md`](./AGENTS.md)。

## JDK（强制）

- **JAVA_HOME**: `F:\demo1\android\.tools\jdk21-full\jdk-21.0.12+8`
- **PATH 前置**: `%JAVA_HOME%\bin`
- **版本**: OpenJDK 21.0.12+8

执行任何 JVM 相关命令前，必须先：

```pwsh
$env:JAVA_HOME = "F:\demo1\android\.tools\jdk21-full\jdk-21.0.12+8"
$env:PATH      = "$env:JAVA_HOME\bin;$env:PATH"
```

禁止使用系统 `java`；构建脚本头部应写入上述环境变量设置。

## Project Skills

Project-specific agent skills are stored in `.agents/skills/`. When a task matches a skill, read the corresponding `.agents/skills/<skill-name>/SKILL.md` before starting work.

完整 Skill 映射表见 [`AGENTS.md`](./AGENTS.md) 中的「通用工程 Skills」章节，来源记录见 [`.agents/skills/SOURCES.md`](./.agents/skills/SOURCES.md)。