<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

## Task Management with Beads (bd)

This project uses **Beads** (`bd`) for task tracking. Always use `bd` commands to manage work.

### Query Available Work
```bash
bd ready --json          # Tasks with no blockers (ready to work)
bd list --json           # All tasks
bd show <id> --json      # Task details
```

### Start Working on a Task
```bash
bd update <id> --status in_progress
```

### Complete a Task
```bash
bd close <id> --reason "Completed: <what was done>"
```

### Create New Tasks (discovered during work)
```bash
bd create "Task title" -p 1 --description "Details"
bd create "Bug found" -p 0 --deps discovered-from:<parent-id>
```

### Add Dependencies
```bash
bd dep add <child> <parent>   # Child is blocked by Parent
```

### Sync to Git (ALWAYS run before ending session)
```bash
bd sync
```

### Current Project Tasks
Run `bd ready` to see tasks available for work. Priority levels:
- **P0**: Critical/Urgent
- **P1**: High priority
- **P2**: Medium priority
- **P3**: Low priority

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
