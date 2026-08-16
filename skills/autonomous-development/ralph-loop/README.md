# ralph-loop

Autonomous task runner that works through a PRD one task at a time using Claude Code in prompt mode.

## How It Works

`ralph.sh` runs a bash loop. Each iteration:

1. Reads `tasks/ralph/{name}/prd.md` and `tasks/ralph/{name}/progress.md` from disk
2. Finds the first incomplete task (`- [ ]` or `- [~]`)
3. Builds a prompt from `prompt-template.md`, injecting the PRD contents, progress log, iteration number, and working directory
4. Calls `claude -p` with that prompt (a fresh, stateless session)
5. Claude marks the task `- [~]` (in progress), implements it, runs verification commands from the PRD, then marks it `- [x]` (done)
6. Claude appends an iteration summary to `progress.md` (files created/modified, decisions made, issues hit)
7. Loop checks for remaining tasks and either continues or exits

No conversation history carries between iterations. The PRD and progress log on disk are the only shared state.

### Signals

Claude can emit two signals during execution:

- `RALPH_COMPLETE` - All tasks are `[x]`, loop exits successfully
- `RALPH_BLOCKED` - Current task can't proceed (missing deps, unclear requirements), skip to next

### SKILL.md

The `SKILL.md` file defines the `/ralph-loop` Claude Code skill. When invoked inside a Claude Code session, it launches `ralph.sh` in the background and polls the PRD file every 60 seconds to report progress. This lets you keep working while Ralph runs.

## Files

| File | Purpose |
|---|---|
| `ralph.sh` | Core loop script |
| `prompt-template.md` | Template injected into each Claude session. Contains instructions for picking a task, implementing it, and updating the PRD/progress files. Uses `{{PRD_CONTENTS}}`, `{{PROGRESS_CONTENTS}}`, `{{ITERATION_NUMBER}}`, and `{{WORKING_DIR}}` placeholders. |
| `prd-template.md` | Blank PRD template for reference |
| `strip_codeblocks.pl` | Perl helper that strips fenced code blocks from markdown so checkbox patterns in code examples aren't counted as real tasks |
| `SKILL.md` | Claude Code skill definition for `/ralph-loop` |

## CLI Usage

```bash
ralph.sh <name>              # Run plan (up to 10 iterations)
ralph.sh <name> 25           # Up to 25 iterations
ralph.sh <name> --dry-run    # Print the prompt without executing
ralph.sh <name> --status     # Show task completion status
ralph.sh --list              # List all plans under tasks/ralph/
```

## PRD Format

The PRD must follow a specific structure so Ralph can parse task status. Tasks use markdown checkboxes:

- `- [ ]` - Incomplete
- `- [~]` - In progress (started by a prior iteration)
- `- [x]` - Done

Each task should include explicit file paths (Ralph starts each iteration with zero context) and acceptance criteria via `**Done when**:` annotations.

See `prd-template.md` for the full template.

## Design Decisions

- **Stateless iterations**: Each Claude session is independent. Crashes and context limits don't break the loop.
- **One task per iteration**: Keeps sessions focused and prevents scope creep.
- **No git operations**: Ralph never commits. You review and commit when ready.
- **Plain bash**: No plugins or framework dependencies. Easy to debug and modify.
