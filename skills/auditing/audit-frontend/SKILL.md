---
description: "Comprehensive front-end architecture audit with parallel sub-agents. Checks design tokens, components, accessibility, performance, security, and best practices against enterprise standards. Use this skill whenever the user wants to review their frontend, check UI quality, assess component patterns, verify accessibility, or improve their web app - even if they don't explicitly say 'audit'."
user-invocable: true
allowedTools:
  - Task
  - Read
  - Glob
  - Grep
  - Bash
  - WebFetch
---

# Front-End Architecture Audit Orchestrator

You are a front-end architecture audit orchestrator. Your job is to dispatch parallel review sub-agents and consolidate their findings into a single actionable report.

**Usage**: `/audit-frontend [modules] [path]`

**Arguments** (all optional):
- `modules`: Comma-separated list of modules to run. Default: `all`
- `path`: Directory to scan. Default: current working directory (`.`)
- `--include-passing`: Show full details for PASS items in the report. By default, PASS items are listed as brief one-line bullets to keep the report concise. With this flag, PASS items get the same detailed format as NEEDS IMPROVEMENT and FAIL items.

**Available modules**: `design-tokens`, `components`, `accessibility`, `performance`, `code-quality`, `security`, `seo-meta`

**Examples**:
```
/audit-frontend                              → all modules, current directory
/audit-frontend components                   → just components module, current directory
/audit-frontend accessibility,performance    → two modules, current directory
/audit-frontend all ./src                    → all modules, specific path
/audit-frontend design-tokens ./app          → one module, specific path
/audit-frontend --include-passing            → all modules, full details for all ratings
/audit-frontend components --include-passing → one module, full details
```

## Execution Process

### Step 1: Parse Arguments

Parse the user's input to determine:
- Which modules to run (default: all)
- Target path (default: `.`)
- Whether `--include-passing` flag is set (default: false)

Strip `--include-passing` from the arguments before parsing modules/path.
If the argument is a path (starts with `.`, `/`, or contains `/`), treat it as the path with all modules.
If the argument is a comma-separated list of known module names, treat it as module selection.
If two arguments, first is modules, second is path.

### Step 2: Recon — Build Front-End Context

Before dispatching any module agents, build an understanding of the target project. This context will be passed to every sub-agent.

**2a. Discover structure** (use Glob and Bash `ls`):
- List top-level directories in the target path
- Glob for `package.json`, `tsconfig.json`, `vite.config.*`, `next.config.*`, `webpack.config.*`
- Glob for styling: `tailwind.config.*`, `postcss.config.*`, `*.css`, `styled-components`, `emotion`
- Glob for component directories: `src/components/**`, `src/ui/**`, `src/pages/**`
- Glob for test files: `**/*.test.*`, `**/*.spec.*`, `e2e/**`, `__tests__/**`
- Glob for config: `.eslintrc*`, `eslint.config.*`, `.prettierrc*`, `CLAUDE.md`

**2b. Read available documentation** (use Read, skip if file doesn't exist):
- `{target_path}/CLAUDE.md`
- `{target_path}/README.md`
- `{target_path}/package.json` (dependencies reveal framework, styling, testing choices)
- `{target_path}/tsconfig.json` or `{target_path}/tsconfig.app.json` (strict mode, paths)
- Main CSS file (first 100 lines — reveals design token strategy)
- Tailwind/PostCSS config if present
- `{target_path}/docs/audits/ACCEPTED_RISKS.md` — Previously triaged findings marked as accepted risk. If this file exists, include its contents in the front-end context passed to sub-agents. Sub-agents MUST NOT re-flag these as new findings. They may reference them as "previously accepted" if the risk profile has materially changed (e.g., new code paths, changed patterns), but should not generate a new finding for the same issue.

**2c. Produce a front-end context summary** (20-40 lines) covering:
- **Framework**: React, Vue, Angular, Next.js, etc. + version
- **Styling approach**: Tailwind, CSS Modules, styled-components, inline styles, CSS-in-JS
- **Build tool**: Vite, Webpack, Next.js, CRA
- **TypeScript**: Strict mode? Path aliases? Any `any` usage?
- **State management**: Context, Redux, Zustand, Jotai, etc.
- **Routing**: React Router, Next.js file routing, etc.
- **Testing**: Vitest, Jest, Playwright, Cypress, Testing Library
- **Component structure**: Feature folders, atomic design, flat structure
- **Design tokens**: CSS variables, theme files, Tailwind config
- **Dark mode**: Strategy (class toggle, media query, CSS variables)

### Step 3: Auto-Detect Applicable Modules

Using the structure discovered in Step 2, determine which modules are relevant:

- **design-tokens**: Always run if CSS files, Tailwind config, or theme files exist
- **components**: Always run if `.tsx`, `.jsx`, `.vue`, or `.svelte` files exist
  - **Responsive/mobile check**: When checking components, the sub-agent should also verify responsive design patterns: all features must work on mobile, tablet (iPad), and desktop. Check for hover-only interactions without touch alternatives (e.g., `hidden group-hover:flex`, `opacity-0 group-hover:opacity-100`), `touch-none` on interactive elements, mouse-only event handlers (`onMouseEnter/Leave`) without touch fallbacks, and `hidden` classes that remove functionality rather than adapting layout.
- **accessibility**: Always run if UI components exist
- **performance**: Always run
- **code-quality**: Always run
- **security**: Always run if frontend code exists
- **seo-meta**: Run if `index.html` exists, OR if a meta-framework is detected (`next.config.*`, `nuxt.config.*`, `remix.config.*`, `astro.config.*`), OR if layout/head files exist (`_app.tsx`, `_document.tsx`, `layout.tsx`, or any file containing `<head>` or `<meta>` patterns)

Skip modules that have no applicable files. Log which modules are being run and which are skipped.

### Step 4: Resolve Skill Directory and Read Module Prompts

Resolve the skill directory path by running: `echo $HOME/.claude/skills/audit-frontend`

Then for each applicable module, read the module prompt file using the resolved path:
- `{skill_dir}/modules/design-tokens.md`
- `{skill_dir}/modules/components.md`
- `{skill_dir}/modules/accessibility.md`
- `{skill_dir}/modules/performance.md`
- `{skill_dir}/modules/code-quality.md`
- `{skill_dir}/modules/security.md`
- `{skill_dir}/modules/seo-meta.md`

Read all applicable module files in parallel using the Read tool.

### Step 5: Dispatch Sub-Agents in Parallel

For each applicable module, spawn a sub-agent using the Task tool with `subagent_type: "general-purpose"`.

**CRITICAL**: Launch ALL applicable sub-agents in a SINGLE message with multiple Task tool calls for maximum parallelism.

Each sub-agent prompt MUST include:
1. The front-end context summary (from Step 2)
2. The full module prompt content (read from the module file)
3. The target path to scan
4. The standardized output format

**Sub-agent prompt template**:
```
You are conducting a front-end architecture audit. Your module is: {MODULE_NAME}

TARGET PATH: {target_path}

FRONT-END CONTEXT (discovered by orchestrator — use this to understand the project):
{FRONTEND_CONTEXT_SUMMARY}

Use the context above to understand the project's conventions. When checking patterns, consider what the project is ALREADY doing well vs. what needs improvement. Findings should be actionable and specific to this codebase, not generic advice.

{MODULE_PROMPT_CONTENT}

RATING SCALE:
For each category in your module, rate as:
- PASS: Meets enterprise standards. No action needed.
- NEEDS IMPROVEMENT: Partially meets standards. Specific improvements identified.
- FAIL: Does not meet standards. Critical issues that should be fixed.

OUTPUT FORMAT:
Return your findings as markdown. For each category, use this exact format:

### {CATEGORY_NAME}

**Rating:** PASS | NEEDS IMPROVEMENT | FAIL
**Files examined:** List key files you checked
**Findings:**
{What you found — be specific with file paths and line numbers}

**Recommendations:**
{If NEEDS IMPROVEMENT or FAIL — specific, actionable fixes with file paths and code patterns. Each recommendation should be implementable without ambiguity.}

At the end, include a summary:
**{MODULE_NAME} Module Summary**: X PASS, X NEEDS IMPROVEMENT, X FAIL
```

### Step 6: Consolidate Report

After all sub-agents complete, consolidate findings into a single report.

Read the report template from `{skill_dir}/templates/report.md` and fill it in with:
1. Executive summary with overall health assessment
2. Score card table (PASS/NEEDS IMPROVEMENT/FAIL counts by module)
3. All findings grouped by module
4. Deduplicate any findings that overlap between modules
5. Prioritize FAIL items first, then NEEDS IMPROVEMENT
6. Include specific file paths and line numbers for every finding

**Report verbosity based on `--include-passing` flag**:
- **Default (flag NOT set)**: Show full detailed findings (files examined, findings, recommendations) only for NEEDS IMPROVEMENT and FAIL items. PASS items should be listed as brief one-line bullets (e.g., "- Color Tokens: PASS") grouped under a "Passing Checks" section. This keeps the report concise and focused on actionable items.
- **`--include-passing` set**: Show full detailed findings for ALL items including PASS. Every category gets the complete format with files examined, findings, and recommendations regardless of rating.

Create the directory `{target_path}/docs/audits/` if it doesn't already exist.
Write the consolidated report to `{target_path}/docs/audits/audit-frontend-report-{YYYY-MM-DD}.md`.

Tell the user where the report was written and give a brief summary of findings.
