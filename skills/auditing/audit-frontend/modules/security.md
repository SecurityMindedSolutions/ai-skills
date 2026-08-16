# Front-End Security Module

Review the front-end application for client-side security vulnerabilities and security best practices.

NOTE: This module focuses on front-end-specific security. For comprehensive security audits including backend, infrastructure, and dependencies, use the `/audit-security` skill.

## Categories to Review

### 1. Content Security Policy (CSP)
- Is a CSP defined (meta tag or server header)?
- Does the CSP block `unsafe-inline` and `unsafe-eval`?
- Are script sources restricted to known origins?
- Is `frame-ancestors` set to prevent clickjacking?
- Are CDN scripts loaded with Subresource Integrity (SRI)?

### 2. Authentication & Session Security
- Are auth tokens stored in HttpOnly cookies (not localStorage/sessionStorage)?
- Is there protection against session fixation?
- Are OAuth state parameters validated?
- Is redirect URL validation in place (block open redirects)?
- Are auth-related environment variables properly scoped (not leaked to client)?

### 3. Input Validation & Sanitization
- Are redirect paths validated (block `//`, `javascript:`, protocol injection)?
- Are URL parameters sanitized before use?
- Is user input sanitized before DOM insertion?
- Are file uploads validated (type, size)?
- Is there protection against prototype pollution?

### 4. XSS Prevention
- Is `dangerouslySetInnerHTML` used? If so, is input sanitized (DOMPurify)?
- Are there `innerHTML`, `outerHTML`, or `document.write` calls?
- Is `eval()`, `new Function()`, or string-based `setTimeout` used?
- Are template literals used to build HTML strings?
- Is user input ever interpolated into `href` or `src` attributes?

### 5. Sensitive Data Exposure
- Are API keys, tokens, or secrets in client-side code?
- Are sensitive values in environment variables prefixed correctly (`VITE_`, `NEXT_PUBLIC_`)?
- Is sensitive data logged to the console?
- Are error messages leaking internal details (stack traces, file paths)?
- Is PII stored in client-side storage?

### 6. Dependency Security
- Are dependencies pinned to exact versions (`.npmrc save-exact=true`)?
- Does `npm audit` report any high/critical vulnerabilities?
- Are there unused dependencies that increase attack surface?
- Is there a lockfile committed (`package-lock.json`, `yarn.lock`)?

### 7. HTTP Security Headers (in HTML meta tags or build config)
- Is `X-Content-Type-Options: nosniff` set?
- Is `Referrer-Policy` configured?
- Is HTTPS enforced (no mixed content)?
- Are cookies configured with `SameSite`, `Secure`, `HttpOnly`?

### 8. Build Security
- Are sourcemaps disabled in production?
- Is the build manifest not exposed publicly?
- Are development tools stripped in production builds?
- Is there `.env` in `.gitignore`?

## Scanning Approach

1. Check `index.html` for CSP meta tags and security headers
2. Search for dangerous DOM APIs (`innerHTML`, `eval`, `document.write`)
3. Review auth flow for token storage and redirect validation
4. Check for hardcoded secrets or API keys
5. Review `.npmrc` and run `npm audit` for dependency issues
6. Check build config for production security settings
7. Verify environment variable handling

## Patterns to Grep For

```
# XSS vectors
dangerouslySetInnerHTML|innerHTML|outerHTML
document\.write|document\.writeln
eval\(|new Function\(|setTimeout\(["']|setInterval\(["']

# Sensitive data exposure
api[_-]?key|apiKey|secret|password|token|credential
PRIVATE_KEY|AWS_SECRET|GOOGLE_API

# Auth patterns
localStorage\.(get|set)Item.*token
sessionStorage\.(get|set)Item.*token
document\.cookie

# Redirect validation
location\.href|window\.location|location\.assign|location\.replace
redirect|returnUrl|next=|callback=

# CSP
Content-Security-Policy|content="default-src
unsafe-inline|unsafe-eval

# HTTP security
X-Frame-Options|X-Content-Type|Referrer-Policy
SameSite|HttpOnly|Secure

# Dependency management
"save-exact"|save-exact=true
```

## Files to Scan
```
index.html
.npmrc
.env*
.gitignore
package.json
package-lock.json
vite.config.*
src/**/*.ts
src/**/*.tsx
src/services/**/*
src/utils/**/*
```
