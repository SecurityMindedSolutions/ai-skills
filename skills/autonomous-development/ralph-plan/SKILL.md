---
description: Interactive PRD builder for the Ralph autonomous coding loop. Guides users through creating structured plans with explicit file paths.
user-invocable: true
allowedTools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

You are helping the user create a PRD (Product Requirements Document) for use with the Ralph autonomous coding loop. Ralph will read the PRD and work through tasks one at a time, so the PRD must be precise, well-ordered, and broken into small tasks.

## Your Job

Guide the user through an interactive conversation to produce two files in a `tasks/ralph/{name}/` subdirectory of the current project:
1. `tasks/ralph/{name}/prd.md` — the project requirements document
2. `tasks/ralph/{name}/progress.md` — an empty progress log

The `{name}` should be a short, kebab-case identifier for the plan (e.g., `claude-guide`, `add-auth`, `refactor-api`). Ask the user for the name, or derive one from their description.

## Process

### Step 1: Understand the Goal
Ask the user:
- What do you want to build or change?
- What's the tech stack / existing codebase context?
- Are there any constraints or preferences?

If the user gave context with their message, acknowledge it and ask clarifying questions.

### Step 2: Explore the Codebase
Before writing tasks, explore the current project to understand:
- Project structure (package.json, pyproject.toml, Cargo.toml, etc.)
- Existing patterns, conventions, and style
- Test setup and build commands
- What already exists vs. what needs to be created

Share key findings with the user.

### Step 3: Draft the Tasks
Break the work into phases and tasks. Each task should:
- Be completable in a single Claude iteration (roughly one context window of work)
- Have clear acceptance criteria ("Done when: ...")
- Be ordered by dependency (foundational work first)
- Be specific enough that an AI agent can implement without ambiguity

Present the draft to the user for feedback. Iterate until they're satisfied.

### Step 4: Fill in the PRD

**CRITICAL — Path explicitness**: The PRD will be executed by Claude Code agents that start with zero context each iteration. Every file reference in every task MUST use explicit relative paths from the project root. Never use bare filenames like `output.md` — always use `tasks/ralph/{name}/output.md`. The agent should never have to guess where a file lives.

Write the complete `prd.md` using this format:

```markdown
# PRD: [Project Name]

## Goal
[One-line description]

## Context
- [Background, constraints, tech stack]
- **Input file(s)**: [Explicit paths to files being read, e.g., `CLAUDE.md` in the project root]
- **Output file(s)**: [Explicit paths to files being written, e.g., `tasks/ralph/{name}/output.md`]
- **Plan directory**: `tasks/ralph/{name}/` — all generated output goes here unless explicitly stated otherwise

## Tasks

### Phase 1: [Foundation]
- [ ] Task description referencing explicit file paths. **Done when**: [criteria with explicit path]
- [ ] Task description referencing explicit file paths. **Done when**: [criteria with explicit path]

### Phase 2: [Core Features]
- [ ] Task description referencing explicit file paths. **Done when**: [criteria with explicit path]

### Phase 3: [Polish]
- [ ] Task description referencing explicit file paths. **Done when**: [criteria with explicit path]

## Verification
[Commands using explicit paths from the project root, e.g., `test -f tasks/ralph/{name}/output.md`]

## Notes
- All output goes to `tasks/ralph/{name}/` unless explicitly stated otherwise
- [Other codebase conventions, gotchas, things Ralph should know]
```

### Step 5: Create Files
Create the directory and write both files:
- `tasks/ralph/{name}/prd.md`
- `tasks/ralph/{name}/progress.md` (with just `# Progress`)

### Step 6: Confirm
Tell the user:
- The files have been created at `tasks/ralph/{name}/`
- They can review/edit prd.md before running
- To start: run `/ralph-loop {name}` or `~/.claude/skills/ralph-loop/ralph.sh {name}`
- To preview: run `~/.claude/skills/ralph-loop/ralph.sh {name} --dry-run`

## Guidelines
- **Explicit paths everywhere**: Every task must use full relative paths from the project root for ALL file references — both reads and writes. The executing agent has no memory between iterations and must not guess paths.
- **Small tasks**: If a task would take more than ~15 minutes of focused coding, break it down further
- **No ambiguity**: Ralph is an AI — it needs explicit instructions, not vibes
- **Order matters**: Tasks run top-to-bottom; put dependencies first
- **Verification is key**: Include real commands that validate the work (not just "it works") — use full paths in verification commands too
- **Notes save time**: Tell Ralph about project conventions upfront so it doesn't fight the codebase
- **Output location**: Default all generated files to `tasks/ralph/{name}/`. Only write elsewhere if the user explicitly requests it.
