# Architecture Decision Log

Record of important design decisions and their rationale.

---

## 2026-06-19: 选择Standard tier harness

- **Decision**: 为AI Advisor Agent项目搭建Standard tier harness工程
- **Reason**: 项目是多会话复杂AI Agent项目，需要完整的harness结构来确保跨会话可靠性
- **Constraints**: 需要维护多个文件（AGENTS.md, feature_list.json, progress.md, DECISIONS.md, session-handoff.md, Makefile等）
- **Alternatives considered**: Minimal tier（仅基础文件）和Full tier（包含CI/CI和gotchas.md），但Standard tier提供了最佳平衡
- **When to revisit**: 当项目进入生产环境或需要团队协作时，考虑升级到Full tier