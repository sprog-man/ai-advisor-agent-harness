# AI Advisor Agent

用于生成决策建议报告或AI知识类问答的Agent+RAG项目，能够拆解用户模糊想法为具体任务步骤。

---

## Quick Start

```bash
make check                 # Full verification (lint + test + integration)
make done                  # Pre-commit doc sync check
make exit                  # Session exit checklist
```

---

## Working Rules

1. **One feature at a time.** Pick exactly one unfinished feature from `feature_list.json`.
2. **Verify before claiming done.** Run `make check` — "looks fine" is not evidence.
3. **Update docs before commit.** Source changes without doc updates → `make done` fails.
4. **Stay in scope.** Don't modify files unrelated to the current feature.
5. **Leave clean state.** Next session can run `make check` immediately.

## Feature Workflow

```
1. Pick feature from feature_list.json
2. Implement code + tests
3. Update progress.md with evidence references
4. Run make check  →  full verification
5. Run make done   →  verify docs synced
6. git add + commit → pre-commit hook re-verifies
7. Update session-handoff.md (end of session)
```

## Verification Commands

| Command | What It Checks |
|---------|----------------|
| `make check` | Lint + tests + integration (code correctness) |
| `make done` | progress.md, feature_list.json, DECISIONS.md up to date with code |
| `make exit` | 5-dimension session exit checklist |

## Session Protocol

**Startup:**
1. Read this file
2. Read `progress.md` + `feature_list.json` — know current state
3. Read `DECISIONS.md` — remember key choices
4. Run `make check` — verify clean starting state

**Exit:**
1. Run `make check` — everything passes
2. Run `make done` — docs synced
3. Update `progress.md` — record what was done
4. Clean temp files, debug code
5. `git add + commit` — hook enforces doc sync
6. Update `session-handoff.md`

## Escalation

- **Architecture decisions**: Add entry to `DECISIONS.md`, or ask user
- **Unclear requirements**: Check docs/, otherwise ask user
- **Repeated test failures**: Log in progress.md, flag for human review