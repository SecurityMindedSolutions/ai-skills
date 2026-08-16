# SEO & Meta Module

Review the application for SEO best practices, meta tag completeness, and social sharing optimization.

## Categories to Review

### 1. HTML Meta Tags
- Is there a `<title>` tag that updates per route?
- Is there a `<meta name="description">` tag?
- Is `<meta name="viewport">` properly configured?
- Is there a canonical URL (`<link rel="canonical">`)?
- Is there a `<html lang="...">` attribute?

### 2. Open Graph & Social Sharing
- Are Open Graph meta tags present (`og:title`, `og:description`, `og:image`, `og:url`)?
- Are Twitter Card meta tags present (`twitter:card`, `twitter:title`, `twitter:description`)?
- Is the `og:image` sized correctly (1200x630px recommended)?
- Do OG tags update per route (for multi-page apps)?

### 3. Structured Data
- Is JSON-LD structured data present where applicable?
- Is the structured data valid (schema.org types)?

### 4. Robots & Crawlability
- Is there a `robots.txt` in the public directory?
- Is there a `sitemap.xml` for multi-page apps?
- Are `<meta name="robots">` tags used appropriately?
- Are client-rendered pages pre-rendered or SSR'd for search engines?

### 5. Performance for SEO
- Does the page pass Core Web Vitals thresholds?
- Is above-the-fold content rendered without JavaScript (SSR/SSG)?
- Are images optimized with alt text (also an accessibility concern)?
- Is there a proper 404 page with appropriate status code?

## Scanning Approach

1. Check `index.html` for meta tags, lang attribute, viewport
2. Search for dynamic title management (Helmet, usePageTitle)
3. Check `public/` directory for robots.txt, sitemap.xml
4. Look for Open Graph and Twitter Card meta tags
5. Check for structured data (JSON-LD scripts)

## Patterns to Grep For

```
# Meta tags
<meta name="description|og:title|og:description|og:image
twitter:card|twitter:title|twitter:description
<link rel="canonical"

# Title management
document\.title|usePageTitle|Helmet|Head

# Structured data
application/ld\+json|schema\.org

# Robots
robots\.txt|sitemap\.xml|<meta name="robots"
```

## Files to Scan
```
index.html
public/robots.txt
public/sitemap.xml
src/**/*.tsx
src/**/*.ts
src/hooks/**/*
```
