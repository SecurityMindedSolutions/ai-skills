# Frontend Security Review Module

Review frontend code (React, Vue, Angular, vanilla JS/TS) for client-side security vulnerabilities.

## Categories to Review

### 1. Cross-Site Scripting (XSS)
<!-- Standards: CWE-79, OWASP-Web-A05:2025 -->
- `dangerouslySetInnerHTML` with user-controlled data
- `document.write()` with unsanitized interpolation
- `innerHTML`, `outerHTML`, `insertAdjacentHTML` with user input
- `eval()`, `new Function()`, `setTimeout/setInterval` with string arguments
- Template literal injection in HTML context (building HTML via string interpolation)
- Missing output encoding when rendering user-provided data

### 2. DOM Manipulation Safety
<!-- Standards: CWE-79, CWE-94 -->
- Direct DOM manipulation with user-controlled values
- URL manipulation (`location.href`, `window.open`, `history.pushState`) with user input
- Event handler injection via user-controlled attributes
- Prototype pollution via `__proto__`, `constructor.prototype`
- `postMessage` handlers without `event.origin` validation (allows cross-origin data injection/exfiltration via iframes or `window.open`)

### 3. Client-Side Storage
<!-- Standards: OWASP-Web-A04:2025, CWE-922 -->
- Sensitive data in `localStorage` or `sessionStorage` (tokens, PII, credentials)
- Sensitive data in cookies without `Secure`, `HttpOnly`, `SameSite` flags
- Unencrypted sensitive data in IndexedDB or Web SQL
- Cache API storing sensitive responses

### 4. Authentication & Token Handling
<!-- Standards: OWASP-Web-A07:2025, OWASP-API2:2023, CWE-522 -->
- Tokens stored in JavaScript-accessible locations (not HttpOnly cookies)
- Auth state managed in client-side storage that can be tampered with
- Missing token expiry validation on the client
- OAuth state parameter not validated on callback
- Open redirect via callback URLs or `next` parameters

### 5. Content Security Policy (CSP)
<!-- Standards: OWASP Proactive Controls C8, OWASP-Web-A02:2025 -->
- Missing or overly permissive CSP headers
- `unsafe-inline` or `unsafe-eval` in CSP
- CDN sources that could be compromised
- Missing `Subresource Integrity` (SRI) on external scripts

### 6. API Communication Security
<!-- Standards: OWASP-Web-A04:2025, NIST-CSF PR.DS -->
- API calls over HTTP instead of HTTPS
- Sensitive data in URL query parameters (logged by proxies, browsers)
- Missing CSRF tokens on state-changing requests
- Response data not validated before rendering

### 7. Third-Party Dependencies
<!-- Standards: OWASP-Web-A03:2025, OWASP-API10:2023 -->
- Inline scripts from untrusted CDNs without SRI
- Third-party widgets with excessive permissions
- Analytics/tracking scripts with access to sensitive DOM content
- Imported libraries with known XSS vulnerabilities

### 8. React-Specific Issues
<!-- Standards: CWE-79 -->
- `dangerouslySetInnerHTML` usage audit
- Ref-based DOM manipulation bypassing React's sanitization
- Server-side rendering (SSR) injection points
- State injection via URL parameters without validation
- `DOMPurify` or equivalent sanitization library usage and configuration

## Scanning Approach

1. Read architecture docs to understand the frontend framework, routing, and auth flow
2. Search for all instances of `dangerouslySetInnerHTML` and HTML string construction
3. Check how user input flows from forms/URL params to rendered output
4. Verify auth tokens are stored securely (HttpOnly cookies, not localStorage)
5. Check CSP headers and inline script usage
6. Review third-party script inclusion for SRI

## Patterns to Grep For

```
# XSS sinks
dangerouslySetInnerHTML|innerHTML|outerHTML|insertAdjacentHTML
document\.write|document\.writeln
eval\(|new Function\(|setTimeout\(.*string|setInterval\(.*string

# DOM manipulation
\.href\s*=|window\.open|location\.(href|assign|replace)
history\.(pushState|replaceState)

# postMessage without origin check
addEventListener\(.*message|onmessage\s*=|postMessage\(

# Client storage
localStorage\.|sessionStorage\.|document\.cookie

# Unsafe rendering
\$\{.*\}.*<|`.*<.*\$\{|template.*literal.*html
v-html|bypassSecurityTrust|\[innerHTML\]

# Auth tokens in JS
token.*localStorage|localStorage.*token|sessionStorage.*jwt
authorization.*header.*variable

# Missing sanitization
\.textContent\s*=.*user|\.innerText\s*=.*user

# Prototype pollution
__proto__|constructor\[|Object\.assign\(.*user

# Open redirect
redirect.*param|next=|returnUrl=|callback=.*http
window\.location.*param|location\.href.*search
```
