# Performance Module

Review the application for front-end performance best practices, bundle optimization, and runtime efficiency.

## Categories to Review

### 1. Bundle Size & Code Splitting
- Are routes lazy-loaded with `React.lazy()` / dynamic `import()`?
- Are heavy third-party libraries tree-shaken or lazy-loaded?
- Is there a build manifest showing chunk sizes?
- Are chunks reasonably sized (main bundle < 250KB gzipped)?
- Is CSS code-split or is there a single large CSS file?

### 2. Asset Optimization
- Are images optimized (WebP/AVIF format, appropriate dimensions)?
- Are fonts loaded efficiently (preload, font-display: swap, subset)?
- Is there a favicon in modern format (SVG or small PNG)?
- Are static assets cache-busted (hash in filenames)?
- Are large assets (images, fonts) lazy-loaded or deferred?

### 3. Rendering Performance
- Are lists virtualized for large datasets (react-window, react-virtualized)?
- Is `useMemo`/`useCallback` used for expensive computations or stable references?
- Are components wrapped in `React.memo` where beneficial?
- Are state updates batched (single state object for related values)?
- Are unnecessary re-renders avoided (proper key usage, stable references)?

### 4. Network Performance
- Are API calls deduplicated (React Query, SWR, or custom caching)?
- Is there retry logic with exponential backoff for transient failures?
- Are API responses cached appropriately?
- Are requests parallelized where possible?
- Is there a loading state strategy (skeleton screens, spinners)?

### 5. Build Configuration
- Are sourcemaps disabled in production?
- Is tree-shaking enabled (ES modules, sideEffects flag)?
- Are vendor chunks separated for better caching?
- Is the build tool configured for optimal output (minification, compression)?
- Are unused dependencies removed from `package.json`?

### 6. Runtime Patterns
- Are event listeners properly cleaned up (useEffect cleanup)?
- Are timers/intervals cleaned up on unmount?
- Are ResizeObserver/IntersectionObserver used efficiently?
- Is there debouncing/throttling on frequent events (scroll, resize, input)?
- Are Web Workers used for CPU-intensive tasks?

### 7. CSS Performance
- Is unused CSS removed (PurgeCSS, Tailwind JIT)?
- Are CSS animations using GPU-accelerated properties (transform, opacity)?
- Is there excessive CSS specificity or deep nesting?
- Are Tailwind arbitrary values minimized (they bypass purging)?

### 8. Core Web Vitals
- Is Interaction to Next Paint (INP) optimized (event handlers under 200ms)?
- Are long tasks broken up (yield to main thread for CPU-intensive operations)?
- Is Largest Contentful Paint (LCP) optimized (preload hero images, server-push critical CSS)?
- Is Cumulative Layout Shift (CLS) minimized (dimensions on images/embeds, font-display: swap)?
- Are there layout shifts from dynamically loaded content without reserved space?

## Scanning Approach

1. Read `package.json` for dependency count and sizes
2. Read build config (vite.config, webpack.config) for optimization settings
3. Check for lazy loading on route definitions
4. Search for memoization patterns and state management efficiency
5. Check asset loading strategy (fonts, images)
6. Review API client for caching and retry patterns
7. Check for event listener cleanup patterns

## Patterns to Grep For

```
# Code splitting
React\.lazy|import\(|Suspense
loadable|@loadable

# Memoization
useMemo|useCallback|React\.memo|memo\(

# State batching issues (multiple useState for related data)
const \[.*useState.*\n.*const \[.*useState

# Event listener cleanup
addEventListener.*\n.*removeEventListener
useEffect.*return.*=>\s*\{

# Timer cleanup
setTimeout|setInterval|clearTimeout|clearInterval

# Large dependencies (check for heavy imports)
import.*moment|import.*lodash[^/]|import.*underscore
from 'moment'|from 'lodash'

# Image optimization
\.(png|jpg|jpeg|gif|bmp)\b
loading="lazy"|loading='lazy'

# Font loading
@font-face|font-display
preload.*font|link.*font

# Sourcemaps in production
sourcemap.*true|devtool.*source

# Debounce/throttle
debounce|throttle|requestAnimationFrame

# Core Web Vitals indicators
requestIdleCallback|scheduler\.postTask|scheduler\.yield
width=|height=|aspect-ratio
font-display
```

## Files to Scan
```
package.json
vite.config.*
webpack.config.*
next.config.*
src/**/*.tsx
src/**/*.jsx
src/**/*.ts
src/**/*.css
public/**/*
```
