#!/usr/bin/env bash
set -euo pipefail

# Ralph Loop Toolkit — autonomous task runner powered by Claude Code
# Usage: ralph.sh [name] [max-iterations] [--dry-run] [--status]
# Plans live in tasks/ralph/{name}/ relative to the current directory.

RALPH_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || realpath "$0")")" && pwd)"
PROMPT_TEMPLATE="$RALPH_DIR/prompt-template.md"

# Defaults
PLAN_NAME=""
MAX_ITERATIONS=10
DRY_RUN=false
STATUS_ONLY=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

usage() {
    cat <<EOF
${BOLD}Ralph Loop Toolkit${NC} — autonomous task runner powered by Claude Code

${BOLD}Usage:${NC}
  ralph.sh <name>              Run plan tasks/ralph/<name>/ (up to 10 iterations)
  ralph.sh <name> 5            Run up to 5 iterations
  ralph.sh <name> --dry-run    Show the prompt that would be sent, don't execute
  ralph.sh <name> --status     Show current PRD completion status
  ralph.sh --list              List all available plans

${BOLD}Plan location:${NC}
  tasks/ralph/<name>/prd.md         Project requirements (created by /ralph-plan)
  tasks/ralph/<name>/progress.md    Auto-maintained progress log

${BOLD}Slash commands (in Claude Code):${NC}
  /ralph-plan    Create a new plan interactively
  /ralph-loop <name>  Run a plan within your Claude Code session
EOF
}

strip_code_blocks() {
    # Remove lines inside fenced code blocks so checkbox patterns
    # in code examples are not counted as real tasks.
    perl "$RALPH_DIR/strip_codeblocks.pl" "$1"
}

count_tasks() {
    local file="$1"
    local pattern="$2"
    local result
    result=$(strip_code_blocks "$file" | grep -c -e "$pattern" 2>/dev/null) || result=0
    echo "$result"
}

count_remaining() {
    local file="$1"
    local stripped unchecked in_progress
    stripped=$(strip_code_blocks "$file")
    unchecked=$(echo "$stripped" | grep -c -e '- \[ \]' 2>/dev/null) || unchecked=0
    in_progress=$(echo "$stripped" | grep -c -e '- \[~\]' 2>/dev/null) || in_progress=0
    echo $((unchecked + in_progress))
}

list_plans() {
    local plans_dir="tasks/ralph"
    if [[ ! -d "$plans_dir" ]]; then
        echo -e "${YELLOW}No plans found. Run /ralph-plan in Claude Code to create one.${NC}"
        return 0
    fi

    echo -e "${BOLD}Available Ralph plans:${NC}"
    echo ""
    for dir in "$plans_dir"/*/; do
        [[ -d "$dir" ]] || continue
        local name
        name=$(basename "$dir")
        local prd="$dir/prd.md"
        if [[ -f "$prd" ]]; then
            local total completed remaining
            total=$(count_tasks "$prd" '- \[.\]')
            completed=$(count_tasks "$prd" '- \[x\]')
            remaining=$(count_remaining "$prd")
            local pct=0
            [[ $total -gt 0 ]] && pct=$((completed * 100 / total))
            echo -e "  ${CYAN}$name${NC}  —  ${completed}/${total} tasks done (${pct}%)"
        else
            echo -e "  ${CYAN}$name${NC}  —  ${RED}missing prd.md${NC}"
        fi
    done
}

show_status() {
    local prd_file="$1"
    local progress_file="$2"
    local name="$3"

    local total remaining completed in_progress
    total=$(count_tasks "$prd_file" '- \[.\]')
    completed=$(count_tasks "$prd_file" '- \[x\]')
    in_progress=$(count_tasks "$prd_file" '- \[~\]')
    remaining=$(count_remaining "$prd_file")

    echo -e "${BOLD}Ralph Status: $name${NC}"
    echo -e "  Total tasks:     ${CYAN}$total${NC}"
    echo -e "  Completed:       ${GREEN}$completed${NC}"
    echo -e "  In progress:     ${BLUE}$in_progress${NC}"
    echo -e "  Remaining:       ${YELLOW}$remaining${NC}"

    if [[ $total -gt 0 ]]; then
        local pct=$((completed * 100 / total))
        echo -e "  Progress:        ${BOLD}${pct}%${NC}"
    fi

    if [[ -f "$progress_file" ]]; then
        local iterations
        iterations=$(grep -c '^## Iteration' "$progress_file" 2>/dev/null || echo 0)
        echo -e "  Iterations run:  ${BLUE}$iterations${NC}"
    fi

    echo ""
    echo -e "${BOLD}Remaining tasks:${NC}"
    strip_code_blocks "$prd_file" | grep -e '- \[ \]' 2>/dev/null | head -20 | while read -r line; do
        echo -e "  ${YELLOW}$line${NC}"
    done
}

build_prompt() {
    local prd_file="$1"
    local progress_file="$2"
    local iteration="$3"

    local prd_contents progress_contents template
    prd_contents=$(cat "$prd_file")
    progress_contents=""
    if [[ -f "$progress_file" ]]; then
        progress_contents=$(cat "$progress_file")
    fi

    template=$(cat "$PROMPT_TEMPLATE")

    # Inject dynamic content into template
    template="${template//\{\{PRD_CONTENTS\}\}/$prd_contents}"
    template="${template//\{\{PROGRESS_CONTENTS\}\}/$progress_contents}"
    template="${template//\{\{ITERATION_NUMBER\}\}/$iteration}"
    template="${template//\{\{WORKING_DIR\}\}/$(pwd)}"

    echo "$template"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --status)
            STATUS_ONLY=true
            shift
            ;;
        --list)
            list_plans
            exit 0
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        [0-9]*)
            MAX_ITERATIONS="$1"
            shift
            ;;
        -*)
            echo -e "${RED}Unknown flag: $1${NC}"
            usage
            exit 1
            ;;
        *)
            if [[ -z "$PLAN_NAME" ]]; then
                PLAN_NAME="$1"
            else
                echo -e "${RED}Unexpected argument: $1${NC}"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Require a plan name (unless --list)
if [[ -z "$PLAN_NAME" ]]; then
    echo -e "${RED}Error: Plan name required${NC}"
    echo ""
    list_plans
    echo ""
    echo -e "Usage: ${BOLD}ralph.sh <name>${NC}"
    exit 1
fi

PLAN_DIR="tasks/ralph/$PLAN_NAME"
PRD_FILE="$PLAN_DIR/prd.md"
PROGRESS_FILE="$PLAN_DIR/progress.md"

# Validate plan exists
if [[ ! -f "$PRD_FILE" ]]; then
    echo -e "${RED}Error: No prd.md found at $PRD_FILE${NC}"
    echo ""
    echo "Create one by running /ralph-plan in a Claude Code session."
    list_plans
    exit 1
fi

# Status mode
if $STATUS_ONLY; then
    show_status "$PRD_FILE" "$PROGRESS_FILE" "$PLAN_NAME"
    exit 0
fi

# Validate other prerequisites
if ! command -v claude &>/dev/null; then
    echo -e "${RED}Error: claude CLI not found in PATH${NC}"
    echo "Install Claude Code: https://docs.anthropic.com/en/docs/claude-code"
    exit 1
fi

if [[ ! -f "$PROMPT_TEMPLATE" ]]; then
    echo -e "${RED}Error: Prompt template missing at $PROMPT_TEMPLATE${NC}"
    exit 1
fi

# Initialize progress file if needed
if [[ ! -f "$PROGRESS_FILE" ]]; then
    cat > "$PROGRESS_FILE" <<'PROGRESS_EOF'
# Progress
PROGRESS_EOF
    echo -e "${CYAN}Created $PROGRESS_FILE${NC}"
fi

# Dry run mode
if $DRY_RUN; then
    echo -e "${BOLD}=== DRY RUN — Prompt for iteration 1 of '$PLAN_NAME' ===${NC}"
    echo ""
    build_prompt "$PRD_FILE" "$PROGRESS_FILE" 1
    exit 0
fi

# Main loop
remaining=$(count_remaining "$PRD_FILE")
if [[ "$remaining" -eq 0 ]]; then
    echo -e "${GREEN}All tasks in $PLAN_NAME are already complete!${NC}"
    exit 0
fi

# Warn if max iterations is less than remaining tasks
if [[ "$remaining" -gt "$MAX_ITERATIONS" ]]; then
    echo -e "${YELLOW}Warning: $remaining tasks remaining but max iterations is $MAX_ITERATIONS${NC}"
    echo -e "${YELLOW}Ralph will stop after $MAX_ITERATIONS tasks. To cover all tasks, run:${NC}"
    echo -e "  ${BOLD}~/.claude/skills/ralph-loop/ralph.sh $PLAN_NAME $remaining${NC}"
    echo ""
    # Skip interactive prompt when there's no TTY (e.g. running in background)
    if [[ -t 0 ]]; then
        read -r -p "Continue with $MAX_ITERATIONS iterations? [Y/n] " response
        if [[ "$response" =~ ^[Nn] ]]; then
            echo "Aborted. Re-run with a higher iteration count."
            exit 0
        fi
    else
        echo -e "${YELLOW}No TTY detected — proceeding automatically.${NC}"
    fi
fi

echo -e "${BOLD}${CYAN}Ralph Loop starting${NC}"
echo -e "  Plan:         $PLAN_NAME"
echo -e "  Directory:    $(pwd)"
echo -e "  PRD:          $PRD_FILE ($remaining tasks remaining)"
echo -e "  Max iters:    $MAX_ITERATIONS"
echo ""

for ((i = 1; i <= MAX_ITERATIONS; i++)); do
    remaining=$(count_remaining "$PRD_FILE")
    if [[ "$remaining" -eq 0 ]]; then
        echo -e "${GREEN}${BOLD}All tasks complete after $((i - 1)) iteration(s)!${NC}"
        exit 0
    fi

    echo -e "${BOLD}${BLUE}--- Iteration $i/$MAX_ITERATIONS ($remaining tasks remaining) ---${NC}"

    prompt=$(build_prompt "$PRD_FILE" "$PROGRESS_FILE" "$i")

    # Run claude with the constructed prompt
    # Unset CLAUDECODE so the child session doesn't think it's nested
    set +e
    output=$(unset CLAUDECODE; claude -p "$prompt" \
        --allowedTools 'Bash(*)' 'Read' 'Write' 'Edit' 'Glob' 'Grep' 'WebFetch' 'WebSearch' \
        2>&1)
    exit_code=$?
    set -e

    if [[ $exit_code -ne 0 ]]; then
        echo -e "${RED}Claude exited with code $exit_code${NC}"
        echo "$output" | tail -20
        echo -e "${YELLOW}Stopping ralph loop.${NC}"
        exit 1
    fi

    # Check for completion/blocked signals
    if echo "$output" | grep -q "RALPH_COMPLETE"; then
        echo -e "${GREEN}${BOLD}Ralph signaled COMPLETE — all tasks done!${NC}"
        exit 0
    fi

    if echo "$output" | grep -q "RALPH_BLOCKED"; then
        echo -e "${YELLOW}${BOLD}Ralph signaled BLOCKED on iteration $i${NC}"
        echo "Check $PROGRESS_FILE for details."
        echo -e "${YELLOW}Continuing to next task...${NC}"
    fi

    echo -e "${GREEN}Iteration $i complete.${NC}"
    echo ""
done

# Final summary
remaining=$(count_remaining "$PRD_FILE")
completed=$(count_tasks "$PRD_FILE" '- \[x\]')
echo -e "${BOLD}${CYAN}--- Ralph Loop Summary: $PLAN_NAME ---${NC}"
echo -e "  Iterations run: $MAX_ITERATIONS"
echo -e "  Tasks completed: ${GREEN}$completed${NC}"
echo -e "  Tasks remaining: ${YELLOW}$remaining${NC}"

if [[ "$remaining" -gt 0 ]]; then
    echo -e "\nRun ${BOLD}~/.claude/skills/ralph-loop/ralph.sh $PLAN_NAME${NC} again to continue."
fi
