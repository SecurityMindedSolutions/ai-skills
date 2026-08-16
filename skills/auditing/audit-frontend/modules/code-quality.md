# Code Quality Module

Review the project's code quality, TypeScript usage, tooling configuration, testing, and developer experience.

## Categories to Review

### 1. TypeScript Configuration
- Is strict mode enabled (`"strict": true`)?
- Are path aliases configured (e.g., `@/` for `src/`)?
- Is `noUnusedLocals` and `noUnusedParameters` enabled?
- Is `any` usage zero or near-zero?
- Are type assertions (`as`) minimized?
- Is `verbatimModuleSyntax` enabled (proper `import type` usage)?

### 2. Import Organization
- Are imports using path aliases (`@/`) instead of deep relative paths (`../../../`)?
- Are `import type` used for type-only imports?
- Is there a consistent import ordering convention?
- Are barrel exports (`index.ts`) used appropriately (not causing circular deps)?

### 3. Linting & Formatting
- Is ESLint configured with TypeScript rules?
- Is a formatter configured (Prettier, Biome, or ESLint formatting rules)?
- Are there lint errors or warnings in the codebase?
- Are React-specific lint rules enabled (react-hooks, react-refresh)?
- Is there a pre-commit hook (husky, lint-staged)?

### 4. Testing Setup
- Is a test framework configured (Vitest, Jest)?
- Is there at least one unit test?
- Are e2e tests configured (Playwright, Cypress)?
- Is test coverage configured?
- Are testing utilities set up (React Testing Library, test setup file)?
- Do tests cover auth, access control, and input validation?

### 5. Error Handling
- Is there an ErrorBoundary at the app level?
- Do async operations handle errors gracefully?
- Are API errors surfaced to the user (toast notifications, inline messages)?
- Is console.error/warn used appropriately (not in production code)?
- Are errors logged with context (not swallowed silently)?

### 6. Hook Patterns
- Do custom hooks follow the `use` prefix convention?
- Are hooks properly cleaning up side effects?
- Are hook dependencies arrays correct (no missing deps, no over-specification)?
- Is `useLayoutEffect` used for DOM measurements and visual updates (not `useEffect`)?
- Are related state values batched into single state objects?

### 7. File & Function Size
- Are components under ~200 lines?
- Are functions under ~50 lines?
- Are there monolithic files that should be split?
- Is there clear separation of concerns (UI, logic, data)?

### 8. Environment & Configuration
- Are environment variables typed and validated?
- Is `.env.example` provided for required variables?
- Are secrets kept out of client bundles?
- Is `NODE_ENV` / build mode used appropriately?

### 9. Internationalization (i18n) Readiness
- Are user-facing strings hardcoded or extracted to a message catalog?
- Are date/time/number formats locale-aware (Intl API)?
- Is text direction (LTR/RTL) considered in layout?
- Are there concatenated strings that would break in translation?

### 10. Browser Compatibility
- Are modern APIs used with appropriate polyfills or fallbacks?
- Is there a browserslist configuration?
- Are CSS features behind vendor prefixes handled (autoprefixer)?
- Is there testing across target browsers documented?

## Scanning Approach

1. Read `tsconfig.json` / `tsconfig.app.json` for TypeScript strictness
2. Read ESLint config for rule coverage
3. Run `npm run lint` to check for current warnings/errors
4. Search for `any` usage across the codebase
5. Check import patterns (relative depth, type imports)
6. Verify test setup and existing test files
7. Check for ErrorBoundary and error handling patterns
8. Measure file sizes and function lengths

## Patterns to Grep For

```
# TypeScript anti-patterns
: any|as any|<any>
@ts-ignore|@ts-expect-error|@ts-nocheck
// eslint-disable

# Import patterns
from '\.\./\.\./\.\./  # Deep relative imports (3+ levels)
import type \{         # Type imports (good pattern)

# Error handling
console\.(error|warn|log)
try\s*\{|catch\s*\(
throw new Error

# Hook patterns
useEffect\s*\(\s*\(\)\s*=>\s*\{
useLayoutEffect
useState|useReducer|useRef|useMemo|useCallback

# Testing
describe\(|it\(|test\(|expect\(
@testing-library|render\(|screen\.
\.spec\.|\.test\.

# Environment variables
import\.meta\.env|process\.env
VITE_|NEXT_PUBLIC_|REACT_APP_

# File organization
export default function|export default class
export \{.*\} from

# i18n patterns
Intl\.|toLocaleString|toLocaleDateString
dir="rtl"|dir="ltr"
```

## Files to Scan
```
tsconfig*.json
eslint.config.*
.eslintrc*
.prettierrc*
package.json
src/**/*.ts
src/**/*.tsx
**/*.test.*
**/*.spec.*
```
