# Autonomous development

Planning and running unattended work.

The two are a pair. `/ralph-plan` writes the PRD, you review and edit it, then
`/ralph-loop` executes it. Both live under `tasks/ralph/{name}/` in the target repo.

---

## `/ralph-plan`

An interactive conversation that produces a PRD the loop can execute.

1. **Understands your goal** - asks what you want to build or change, the tech stack, and any constraints
2. **Explores the codebase** - reads project structure, existing patterns, test setup, and build commands to ground the plan in reality
3. **Drafts tasks** - breaks the work into phased, ordered tasks with acceptance criteria, each sized to fit a single iteration
4. **Writes the PRD** - creates `tasks/ralph/{name}/prd.md` with explicit file paths everywhere
5. **Creates the progress log** - initializes `tasks/ralph/{name}/progress.md`

`{name}` is a short kebab-case identifier such as `add-auth` or `refactor-api`, either
given by you or derived from your description.

### Key principles

**Explicit paths everywhere.** Every task references files by full relative path from
the project root. Never `output.md`, always `tasks/ralph/my-plan/output.md`. The
executing agent has no memory between iterations.

**Small tasks.** If a task would take more than roughly 15 minutes of focused coding,
it gets broken down further.

**Order matters.** Tasks run top to bottom, so dependencies go first.

**Verification commands.** The PRD includes real lint, build and test commands that
Ralph runs after each task to check nothing is broken.

### Output

```
tasks/ralph/{name}/
  prd.md         # The plan: tasks with checkboxes, acceptance criteria, verification commands
  progress.md    # Empty log that Ralph populates as it works
```

Review and edit `prd.md` before running, then start execution with `/ralph-loop {name}`.

---

## `/ralph-loop`

`ralph.sh` runs a bash loop. Each iteration:

1. Reads `tasks/ralph/{name}/prd.md` and `tasks/ralph/{name}/progress.md` from disk
2. Finds the first incomplete task (`- [ ]` or `- [~]`)
3. Builds a prompt from `prompt-template.md`, injecting the PRD contents, progress log, iteration number, and working directory
4. Calls `claude -p` with that prompt, as a fresh stateless session
5. Claude marks the task `- [~]` (in progress), implements it, runs the PRD's verification commands, then marks it `- [x]` (done)
6. Claude appends an iteration summary to `progress.md`: files created and modified, decisions made, issues hit
7. The loop checks for remaining tasks and either continues or exits

No conversation history carries between iterations. The PRD and progress log on disk
are the only shared state.

### Signals

- `RALPH_COMPLETE` - all tasks are `[x]`, loop exits successfully
- `RALPH_BLOCKED` - current task cannot proceed (missing deps, unclear requirements), skip to next

### Files

| File | Purpose |
|---|---|
| `ralph.sh` | Core loop script |
| `prompt-template.md` | Template injected into each Claude session. Contains instructions for picking a task, implementing it, and updating the PRD and progress files. Uses `{{PRD_CONTENTS}}`, `{{PROGRESS_CONTENTS}}`, `{{ITERATION_NUMBER}}` and `{{WORKING_DIR}}` placeholders. |
| `prd-template.md` | Blank PRD template for reference |
| `strip_codeblocks.pl` | Perl helper that strips fenced code blocks from markdown so checkbox patterns in code examples are not counted as real tasks |
| `SKILL.md` | Skill definition for `/ralph-loop`, which launches `ralph.sh` in the background and polls the PRD every 60 seconds so you can keep working while it runs |

### CLI usage

```bash
ralph.sh <name>              # Run plan (up to 10 iterations)
ralph.sh <name> 25           # Up to 25 iterations
ralph.sh <name> --dry-run    # Print the prompt without executing
ralph.sh <name> --status     # Show task completion status
ralph.sh --list              # List all plans under tasks/ralph/
```

### PRD format

The PRD must follow a specific structure so Ralph can parse task status. Tasks use
markdown checkboxes: `- [ ]` incomplete, `- [~]` in progress (started by a prior
iteration), `- [x]` done.

Each task should include explicit file paths, because Ralph starts each iteration with
zero context, and acceptance criteria via `**Done when**:` annotations. See
`ralph-loop/prd-template.md` for the full template.

### Design decisions

- **Stateless iterations.** Each session is independent, so crashes and context limits do not break the loop.
- **One task per iteration.** Keeps sessions focused and prevents scope creep.
- **No git operations.** Ralph never commits. You review and commit when ready.
- **Plain bash.** No plugins or framework dependencies, easy to debug and modify.
