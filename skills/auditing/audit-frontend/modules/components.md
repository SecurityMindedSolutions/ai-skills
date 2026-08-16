# Component Architecture Module

Review component design, reusability, composition patterns, and structural consistency.

## Categories to Review

### 1. Component Composition & Reusability
- Are there shared UI components (Button, Card, Modal, Spinner, etc.)?
- Are components composable (accept `children`, `className`, render props)?
- Is there component duplication (similar UI built in multiple places)?
- Do shared components live in a dedicated directory (`components/ui/`, `components/shared/`)?
- Are there barrel exports (`index.ts`) for component directories?

### 2. Props & TypeScript Patterns
- Are component props explicitly typed (interfaces, not inline)?
- Are discriminated unions used for variant props (instead of optional prop soup)?
- Is `any` used anywhere? (Search for `: any`, `as any`)
- Are generic components properly typed?
- Are default props handled idiomatically (destructuring defaults, not `defaultProps`)?

### 3. State Management
- Is state lifted appropriately (not too high, not too low)?
- Are contexts used for cross-cutting concerns (theme, auth, notifications)?
- Is there unnecessary prop drilling (3+ levels)?
- Are expensive computations memoized (`useMemo`, `useCallback`) where needed?
- Is state batched properly (single state object vs multiple `useState` for related values)?

### 4. Component File Structure
- Do components follow a consistent file naming convention?
- Are components organized logically (by feature, by type, or hybrid)?
- Is code splitting implemented (lazy loading for routes/heavy components)?
- Are page components separate from reusable UI components?
- Is there a clear separation between layout, page, and UI components?

### 5. Shared Component Library Completeness
- Does the project have components for: Button, Card, Modal, Spinner/Loading, Toast/Notification, Input/Form fields?
- Are icon components centralized (shared icon library vs inline SVGs scattered)?
- Is there a Logo component that handles different sizes/variants?
- Are there layout primitives (Stack, Grid, Container)?

### 6. Error & Loading States
- Do async components handle loading, error, and empty states?
- Is there an ErrorBoundary wrapping the app or major sections?
- Are Suspense boundaries used with lazy-loaded components?
- Do forms show validation errors inline?
- Are error messages user-friendly (not raw error strings)?

### 7. Constants & Configuration
- Are magic strings centralized (app name, company name, URLs)?
- Is configuration environment-aware (dev vs prod)?
- Are feature flags used for incomplete features?
- Are API endpoints centralized (not hardcoded in components)?

## Scanning Approach

1. Map the component directory structure
2. Read shared UI components to assess composability and API design
3. Search for component duplication (similar JSX patterns in multiple files)
4. Check TypeScript strictness and prop typing patterns
5. Verify state management patterns
6. Check for centralized constants and configuration

## Patterns to Grep For

```
# TypeScript anti-patterns
: any|as any
React\.FC|React\.FunctionComponent  # Prefer function declarations
defaultProps

# State management
useState\(|useReducer\(|useContext\(
useMemo\(|useCallback\(|React\.memo\(

# Component patterns
React\.lazy\(|Suspense
ErrorBoundary|getDerivedStateFromError|componentDidCatch
children\?:|children:|ReactNode

# Hardcoded strings (should be constants)
'http://|'https://  # Hardcoded URLs
"http://|"https://

# Prop drilling indicators (components passing many props through)
\.\.\.(props|rest)

# Code splitting
import\(|React\.lazy

# Inline SVGs (should be icon components)
<svg[\s>]
```

## Files to Scan
```
src/components/**/*.tsx
src/components/**/*.jsx
src/pages/**/*.tsx
src/contexts/**/*.tsx
src/hooks/**/*.ts
src/config/**/*.ts
src/constants/**/*.ts
```
