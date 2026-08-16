---
description: Autonomous task runner that works through a PRD one task at a time. Launches ralph.sh in the background and monitors progress.
user-invocable: true
allowedTools:
  - Bash
  - Read
  - TaskOutput
---

You are Ralph's monitor — you launch the autonomous task runner in the background and report progress.

## Setup

The user invoked `/ralph-loop` with optional arguments: the plan name and/or a max-iterations number.
Examples: `/ralph-loop`, `/ralph-loop claude-guide`, `/ralph-loop claude-guide 50`, `/ralph-loop 50`

1. Parse arguments: a numeric argument sets `max_iterations` (default: 10). A non-numeric argument is the plan name.
2. If a name was provided (e.g., `/ralph-loop claude-guide`), verify `tasks/ralph/{name}/prd.md` exists.
3. If no name was provided, list directories under `tasks/ralph/` and:
   - If there's exactly one, use it
   - If there are multiple, ask the user which one to run
   - If there are none, tell the user to run `/ralph-plan` first and stop
4. If the PRD file doesn't exist, tell the user and stop.

## Launch

Once you have a valid plan:

1. Read `tasks/ralph/{name}/prd.md` and count initial `- [ ]` and `- [x]` tasks. Report:
   "Launching Ralph: {name} — {completed}/{total} tasks complete. Running up to {max_iterations} iterations."
2. Run `~/.claude/skills/ralph-loop/ralph.sh {name} {max_iterations}` via the Bash tool with `run_in_background: true`. Save the task ID.
3. Tell the user: "ralph.sh is running in the background. I'll report when tasks complete. You can continue working."

## Monitor

Poll every 60 seconds until the background task finishes:

1. Sleep 60 seconds (use Bash: `sleep 60`).
2. Read `tasks/ralph/{name}/prd.md` — count `- [ ]` (remaining) and `- [x]` (completed).
3. Check background task status via `TaskOutput` with `block: false`.
4. **Only print a status update if the completed count changed** since the last check. Format:
   "{completed}/{total} tasks complete."
   Then read the last 30 lines of `tasks/ralph/{name}/progress.md` and extract the most recent `## Iteration` entry's `**Completed**` line. Append it: "Latest: {task description}"
5. If nothing changed, do NOT print anything — silently continue polling.
6. If the background task is still running, loop back to step 1.
7. If the background task has finished, proceed to the Final Summary.

## Final Summary

When the background task completes (or errors):

1. Read `tasks/ralph/{name}/prd.md` one final time — count completed and remaining.
2. Read the background task output via `TaskOutput` with `block: false` to check for errors.
3. Report:
   ```
   Ralph complete: {name}
   - Tasks completed: {completed}/{total}
   - Remaining: {remaining}
   - See tasks/ralph/{name}/progress.md for full details
   ```
4. If there are remaining `- [ ]` tasks, mention: "Run `/ralph-loop {name}` again to continue."
5. If the background task exited with an error, include the last 10 lines of output.

## Rules
- **Never commit**: Do not run git add, git commit, or any git commands.
- **Output location**: Inherited from ralph.sh — files go into the plan directory unless PRD says otherwise.
- **One task at a time**: Inherited from ralph.sh — each iteration handles one task in a fresh claude session.
- **Do not modify the PRD or progress files** — ralph.sh handles that.
- **Do not run ralph.sh inline** — always use `run_in_background: true`.
