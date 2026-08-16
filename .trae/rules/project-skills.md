---
description: Project-level Agent Skills registry and usage mapping for CampusMateAI
globs:
  - "**/*"
alwaysApply: true
---

# CampusMateAI Project Skills

Project-specific agent skills are stored in `.agents/skills/`. When a task clearly matches a skill, read the corresponding `.agents/skills/<skill-name>/SKILL.md` before implementing or modifying code.

## Skill Mapping

| Trigger | Skill |
|---------|-------|
| Planning complex features | `writing-plans` |
| Executing existing plans | `executing-plans` |
| Complex bugs | `systematic-debugging` / `debugging-strategies` / `debugging-and-error-recovery` |
| New features | `test-driven-development` |
| Before claiming completion | `verification-before-completion` |
| Requesting code review | `requesting-code-review` / `code-review-and-quality` / `code-review-excellence` |
| Receiving code review | `receiving-code-review` |
| Subagent-driven dev | `subagent-driven-development` / `dispatching-parallel-agents` |
| Git worktree | `using-git-worktrees` / `finishing-a-development-branch` |
| Brainstorming | `brainstorming` |
| API contract design | `api-and-interface-design` / `api-design-principles` |
| Web UI engineering | `frontend-ui-engineering` / `frontend-design` |
| Incremental implementation | `incremental-implementation` |
| CI/CD | `ci-cd-and-automation` |
| Context engineering | `context-engineering` |
| Code simplification | `code-simplification` |
| Docs / ADRs | `documentation-and-adrs` |
| Observability | `observability-and-instrumentation` |
| Git workflow | `git-workflow-and-versioning` |
| Android Compose | `jetpack-compose` |
| CameraX / Camera | `camera` |
| On-device AI / LiteRT | `device-ai` |
| Android Navigation | `navigation` |
| Android Performance | `performance` / `profilers` |
| Android Testing | `testing` |
| Android Security | `security` |
| Android Build | `build-system` |
| Android DevTools | `devtools` |
| Vue pages | `vue-best-practices` |
| Vue Router | `vue-router-best-practices` |
| Pinia | `vue-pinia-best-practices` |
| Vue testing | `vue-testing-best-practices` |
| Vue debugging | `vue-debug-guides` |
| Adaptable Composable | `create-adaptable-composable` |
| FastAPI | `fastapi-templates` |
| Python testing | `python-testing-patterns` |
| RAG | `rag-implementation` |
| Hybrid search | `hybrid-search-implementation` |
| Embedding | `embedding-strategies` |
| Similarity search | `similarity-search-patterns` |
| LLM evaluation | `llm-evaluation` |
| Auth implementation | `auth-implementation-patterns` |
| E2E testing | `e2e-testing-patterns` / `webapp-testing` |
| Creating new skills | `skill-creator` |
| WeChat Mini Program copy | `miniapp-user-facing-copy-trim` |
| WeChat scaffold | `miniapp-official-scaffold-alignment` |
| WeChat DevTools recovery | `miniapp-devtools-recovery` |
| WeChat deploy | `wechat-miniprogram-auto-port-deploy` |

Detailed specs are in each skill's own `SKILL.md`. Source records: `.agents/skills/SOURCES.md`.