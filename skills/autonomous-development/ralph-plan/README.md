# ralph-plan

Interactive PRD builder for the Ralph autonomous coding loop. This is a Claude Code skill that guides you through creating a structured plan.

## How It Works

When you run `/ralph-plan` inside a Claude Code session, it starts a conversation that:

1. **Understands your goal** - Asks what you want to build/change, the tech stack, and any constraints
2. **Explores the codebase** - Reads project structure, existing patterns, test setup, and build commands to ground the plan in reality
3. **Drafts tasks** - Breaks the work into phased, ordered tasks with acceptance criteria. Each task is sized to fit a single Claude iteration.
4. **Writes the PRD** - Creates `tasks/ralph/{name}/prd.md` with explicit file paths everywhere (Ralph starts each iteration with zero context)
5. **Creates the progress log** - Initializes `tasks/ralph/{name}/progress.md`

The `{name}` is a short kebab-case identifier (e.g., `add-auth`, `refactor-api`) that you provide or it derives from your description.

## Key Principles

**Explicit paths everywhere**: Every task references files using full relative paths from the project root. Never `output.md`, always `tasks/ralph/my-plan/output.md`. The executing agent has no memory between iterations.

**Small tasks**: If a task would take more than ~15 minutes of focused coding, it gets broken down further. This keeps each iteration focused.

**Order matters**: Tasks run top-to-bottom. Dependencies go first.

**Verification commands**: The PRD includes real commands (lint, build, test) that Ralph runs after each task to validate nothing is broken.

## Output

After the conversation, you get:

```
tasks/ralph/{name}/
  prd.md         # The plan - tasks with checkboxes, acceptance criteria, verification commands
  progress.md    # Empty log that Ralph populates as it works
```

Review and edit `prd.md` before running. Then start execution with `/ralph-loop {name}`.
