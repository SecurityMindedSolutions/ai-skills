# Design Tokens & Theming Module

Review the project's design token system, theming architecture, and visual consistency.

## Categories to Review

### 1. Color Token Architecture
- Are colors defined as reusable tokens (CSS custom properties, Tailwind config, or theme file)?
- Are raw hex/rgb values hardcoded in components? (Search for patterns like `#[0-9a-fA-F]{3,8}`, `rgb(`, `hsl(`)
- Do color tokens follow a semantic naming convention (e.g., `--color-text-primary` not `--blue-500`)?
- Are there separate tokens for light and dark mode?
- Is there a single source of truth for colors, or are they scattered?

### 2. Typography System
- Is there a defined type scale (font sizes, weights, line heights)?
- Are font families defined as tokens, not hardcoded strings?
- Are there consistent heading styles (h1-h6)?
- Is there a base font size and does the scale derive from it?
- Are font imports efficient (variable fonts, subset characters)?

### 3. Spacing & Layout Tokens
- Is spacing consistent (e.g., 4px/8px base unit, Tailwind's default scale)?
- Are spacing values from the token system or arbitrary?
- Are breakpoints defined centrally and used consistently?
- Is z-index managed (defined scale vs arbitrary values)?

### 4. Dark Mode Implementation
- Is dark mode implemented via CSS (class/media query) or JavaScript?
- Does the theme toggle use `useLayoutEffect` (not `useEffect`) to prevent flash?
- Are all components dark-mode aware?
- Is there a FOUC (Flash of Unstyled Content) on page load?
- Is theme preference persisted (localStorage)?

### 5. Design Token Consistency
- Are tokens actually USED consistently, or are there one-off overrides?
- Do all components reference the same token set?
- Are there duplicate or conflicting token definitions?
- Is the token naming convention consistent (kebab-case, camelCase, etc.)?

### 6. Tailwind-Specific Checks (if applicable)
- Is `@theme` or `theme.extend` used properly for custom tokens?
- Are arbitrary values (`[24px]`, `[#ff0000]`) used instead of configured tokens?
- Is the Tailwind config DRY (no duplicate definitions)?
- Are `dark:` variants used consistently?
- Is the CSS file using `@import "tailwindcss"` (v4) or `@tailwind` directives (v3)?
- Are Tailwind utility classes consistent (no mixing of `p-4` and `p-[16px]` for the same spacing)?
- Are responsive breakpoint prefixes used consistently (`sm:`, `md:`, `lg:`) vs arbitrary `max-w-[768px]`?
- Is there a Tailwind class ordering convention (official Prettier plugin or manual)?

## Scanning Approach

1. Read the main CSS/theme file to understand the token architecture
2. Read Tailwind config (if present) for custom theme extensions
3. Grep for hardcoded color values in component files
4. Grep for hardcoded font families and sizes
5. Check dark mode implementation pattern
6. Verify token usage consistency across components

## Patterns to Grep For

```
# Hardcoded colors (should be tokens)
#[0-9a-fA-F]{3,8}[^-]
rgb\(|rgba\(|hsl\(|hsla\(

# Hardcoded fonts (should be tokens)
font-family:|fontFamily
'(Arial|Helvetica|Times|Verdana|Georgia|Courier)'

# Hardcoded spacing (look for arbitrary Tailwind values)
\[(\d+)px\]|\[(\d+)rem\]

# Dark mode patterns
useEffect.*dark|useLayoutEffect.*dark
class.*dark|\.dark\s
prefers-color-scheme

# Z-index arbitrary values
z-\[\d+\]|z-index:\s*\d{2,}

# Tailwind arbitrary values (potential token gaps)
\[\#[0-9a-fA-F]+\]
```

## Files to Scan
```
**/*.css
**/*.scss
**/*.less
tailwind.config.*
postcss.config.*
**/theme.*
**/tokens.*
**/colors.*
**/typography.*
**/*.tsx
**/*.jsx
```
