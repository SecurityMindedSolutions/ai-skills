# Frontend Audit Skill

Comprehensive front-end architecture audit that dispatches parallel sub-agents to check design systems, components, accessibility, performance, and code quality against enterprise standards.

## Modules

| Module | What It Checks |
|---|---|
| **design-tokens** | CSS variable usage, theme consistency, hardcoded values, dark mode strategy, spacing/color systems |
| **components** | Component structure, prop patterns, reusability, composition, shared component usage |
| **accessibility** | ARIA attributes, keyboard navigation, focus management, color contrast, screen reader support |
| **performance** | Bundle size, lazy loading, image optimization, render performance, caching strategies |
| **code-quality** | TypeScript strictness, linting, naming conventions, file organization, dead code |
| **security** | XSS vectors, client-side secret storage, CSP, postMessage handling, third-party script risks |
| **seo-meta** | Meta tags, Open Graph, structured data, canonical URLs, sitemap |

## Usage

```
/audit-frontend                              # All modules, current directory
/audit-frontend components                   # Just components module
/audit-frontend accessibility,performance    # Two specific modules
/audit-frontend all ./src                    # All modules, specific path
/audit-frontend design-tokens ./app          # One module, specific path
```

## Output

Report is written to `{target_path}/docs/audits/audit-frontend-report-{YYYY-MM-DD}.md` containing:

- Executive summary with overall health assessment
- Score card table (PASS / NEEDS IMPROVEMENT / FAIL counts by module)
- All findings grouped by module with specific file paths and line numbers
- Prioritized recommendations

### Rating Scale

| Rating | Meaning |
|---|---|
| **PASS** | Meets enterprise standards. No action needed. |
| **NEEDS IMPROVEMENT** | Partially meets standards. Specific improvements identified. |
| **FAIL** | Does not meet standards. Critical issues that should be fixed. |

### Finding Format

Each finding includes:

- **Rating** — PASS, NEEDS IMPROVEMENT, or FAIL
- **Files examined** — Key files that were checked
- **Findings** — What was found, with file paths and line numbers
- **Recommendations** — Specific, actionable fixes (for non-PASS ratings)

## File Structure

```
audit-frontend/
├── SKILL.md              # Orchestrator prompt and execution logic
├── README.md             # This file
├── modules/
│   ├── design-tokens.md  # Design token and theming rules
│   ├── components.md     # Component architecture rules
│   ├── accessibility.md  # Accessibility (a11y) rules
│   ├── performance.md    # Performance optimization rules
│   ├── code-quality.md   # Code quality and conventions rules
│   ├── security.md       # Client-side security rules
│   └── seo-meta.md       # SEO and meta tag rules
└── templates/
    └── report.md         # Consolidated report template
```

## Customization

- **Add a module** — Create a new `.md` file in `modules/` following the existing format and add the module name to `SKILL.md`
- **Modify rules** — Edit module files to adjust checks, thresholds, or category definitions
- **Change report format** — Edit `templates/report.md` to customize the output structure
