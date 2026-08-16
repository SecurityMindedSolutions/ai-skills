# Accessibility (a11y) Module

Review the application for WCAG 2.1 AA compliance and accessibility best practices.

## Categories to Review

### 1. Semantic HTML
- Are semantic elements used (`<nav>`, `<main>`, `<aside>`, `<header>`, `<footer>`, `<section>`, `<article>`)?
- Is there a single `<main>` landmark?
- Are headings hierarchical (h1 → h2 → h3, no skipped levels)?
- Are lists used for list content (`<ul>`, `<ol>`, `<dl>`)?
- Are `<button>` elements used for actions (not `<div onClick>`)?

### 2. ARIA Attributes
- Do interactive custom widgets have appropriate `role` attributes?
- Do modals/dialogs have `role="dialog"` and `aria-modal="true"`?
- Do expandable sections have `aria-expanded`?
- Do navigation elements have `aria-label` or `aria-labelledby`?
- Is `aria-hidden="true"` on decorative elements (icons, dividers)?
- Is `aria-current="page"` used for active navigation items?
- Are `aria-live` regions used for dynamic content updates (toasts, form errors)?

### 3. Keyboard Navigation
- Are all interactive elements focusable and operable with keyboard?
- Is there a visible focus indicator on all focusable elements?
- Do modals trap focus (Tab/Shift+Tab cycles within modal)?
- Do modals restore focus on close?
- Is there a skip-to-content link?
- Does Escape close modals and overlays?
- Is tab order logical (follows visual layout)?

### 4. Form Accessibility
- Do all form inputs have associated `<label>` elements?
- Are required fields indicated (both visually and with `aria-required`)?
- Are validation errors linked to inputs via `aria-describedby`?
- Are error messages announced to screen readers (`aria-live` or `role="alert"`)?
- Do submit buttons indicate loading state (disabled + `aria-busy`)?
- Do inputs have `autocomplete` attributes for common fields (name, email, address)?
- Are error suggestions provided alongside validation messages (WCAG 3.3.3)?

### 5. Image & Media Accessibility
- Do all `<img>` elements have `alt` attributes?
- Are decorative images marked with `alt=""` or `aria-hidden="true"`?
- Do icon-only buttons have accessible text (`aria-label`, visually hidden text)?
- Are SVG icons properly hidden from assistive technology when decorative?

### 6. Color & Contrast
- Does text meet minimum contrast ratio (4.5:1 for normal text, 3:1 for large text)?
- Is information conveyed by more than just color (icons, text, patterns)?
- Do focus indicators have sufficient contrast?
- Does dark mode maintain adequate contrast ratios?

### 7. Dynamic Content
- Are toast notifications announced to screen readers?
- Are loading states announced (spinner + sr-only text)?
- Do route changes announce the new page title?
- Are client-side errors announced to assistive technology?
- Does `document.title` update on navigation?

### 8. Screen Reader Support
- Is there visually hidden text (`.sr-only`) for context that's visual-only?
- Are decorative elements hidden from screen readers?
- Do icon buttons have accessible names?
- Is the page usable with a screen reader (logical reading order, meaningful labels)?

### 9. Reflow & Visual Adaptation (WCAG 1.4.10-1.4.13)
- Does content reflow at 320px CSS width without horizontal scrolling (1.4.10)?
- Are text spacing adjustments tolerated (line-height 1.5x, letter-spacing 0.12em, word-spacing 0.16em) without content loss (1.4.12)?
- Is content visible on hover/focus dismissible, hoverable, and persistent (1.4.13)?
- Are there content-on-hover patterns that disappear when the user moves their cursor?

### 10. Timing & Motion (WCAG 2.2.1-2.2.2, 2.3.3)
- Are `prefers-reduced-motion` media queries used for animations?
- Can users pause, stop, or hide auto-updating content (2.2.2)?
- Are there animations lasting more than 5 seconds without user control?
- Does Tailwind `transition-*` / `animate-*` respect `motion-reduce:` variants?

## Scanning Approach

1. Check `index.html` for lang attribute, skip link, viewport meta
2. Search all components for ARIA attributes and semantic HTML usage
3. Check Modal/Dialog components for focus trap and ARIA
4. Check form components for label associations
5. Check navigation for `aria-current`, `aria-expanded`
6. Check images and icons for alt text and aria-hidden
7. Check toast/notification system for aria-live
8. Verify document title updates on route changes

## Patterns to Grep For

```
# Missing semantic HTML (anti-patterns)
<div\s+onClick|<span\s+onClick  # Should be <button>
role="button"                    # Usually means a div is being used as a button

# ARIA attributes (look for presence)
aria-label|aria-labelledby|aria-describedby
aria-expanded|aria-hidden|aria-modal|aria-current
aria-live|aria-busy|aria-required
role="dialog"|role="alert"|role="navigation"|role="main"

# Keyboard handling
onKeyDown|onKeyUp|onKeyPress
tabIndex|tabindex

# Focus management
focus\(\)|\.focus\(|useRef.*focus|focusTrap|FocusTrap
document\.activeElement

# Skip link
skip-to|skip-nav|skipnav|#main-content

# Screen reader only text
sr-only|visually-hidden|screenReaderOnly

# Alt text
alt="|alt='|alt=\{

# Heading hierarchy
<h1|<h2|<h3|<h4|<h5|<h6

# Document title
document\.title|usePageTitle|Helmet

# Reduced motion
prefers-reduced-motion|motion-reduce|motion-safe
animate-|transition-

# Reflow patterns
overflow-x|overflow-hidden|white-space.*nowrap|min-width.*\d+px
```

## Files to Scan
```
index.html
src/**/*.tsx
src/**/*.jsx
src/components/**/*
src/hooks/**/*
```
