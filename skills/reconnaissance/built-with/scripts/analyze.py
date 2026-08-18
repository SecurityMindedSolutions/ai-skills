#!/usr/bin/env python3
"""
built-with: passive, headless frontend recon of a web app.

No browser. Pure stdlib (urllib). Given an app URL it:
  1. fetches the root HTML + response headers (records the redirect chain),
  2. discovers every same-origin JS/CSS asset referenced by the page and,
     recursively, every additional chunk those bundles reference,
  3. downloads the JS and extracts: API endpoints, referenced hostnames,
     third-party vendor signatures, the CSP allow-lists (a map of the whole
     stack), framework/build tooling, and public config tokens,
  4. optionally probes the primary backend + auth hosts for tech-fingerprint
     headers (server, RFC-7807 problem+json, CORS allow-headers),
  5. writes report.json + report.md into the output directory.

Everything is best-effort and bounded so a hostile or huge target can't hang
or blow up disk. Public browser tokens (Sentry DSN, WorkOS client_id,
Fingerprint public key) are reported because they are already shipped to every
visitor; the script never attempts to find server-side secrets.

Usage:
    python analyze.py <url> [--out DIR] [--max-files N] [--max-mb N] [--no-probe]
"""
import argparse, json, os, re, ssl, sys, time
from datetime import datetime, timezone
from urllib import request, error
from urllib.parse import urljoin, urlparse
from http.client import HTTPResponse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Hosts that show up in library source/comments and are almost never the
# target's own infrastructure. Recorded under "other", kept out of the vendor
# and primary-host signal.
NOISE_HOSTS = {
    "www.w3.org", "w3.org", "react.dev", "reactjs.org", "reactrouter.com",
    "redux.js.org", "redux-toolkit.js.org", "github.com", "example.com",
    "www.example.com", "foo.bar", "schema.org", "www.mozilla.org", "fb.me",
    "goo.gl", "bit.ly", "ycombinator.com", "www.ycombinator.com", "office.com",
    "yourwebsite.com", "yourcompany.com", "localhost", "radix-ui.com",
    "mantine.dev", "fontawesome.com", "docs.sentry.io", "vitejs.dev",
}

# Vendor catalog. Each entry: patterns matched (case-insensitive) against the
# combined asset text + hostnames + CSP; a coarse category to seed the
# internal/product/integration read; and a short note. Category is a hint the
# human/Claude refines - a hostname alone can't always tell product from ops.
VENDORS = [
    # auth / identity
    ("WorkOS",            ["workos.com", "workos", "authkit"],                 "auth",        "Auth / SSO / user management (AuthKit)"),
    ("Auth0",             ["auth0.com", "auth0"],                              "auth",        "Auth / identity"),
    ("Clerk",             ["clerk.com", "clerk.dev", "clerk.accounts"],        "auth",        "Auth / identity"),
    ("Okta",              ["okta.com", "okta-credentials", "oktacdn"],         "auth",        "Enterprise SSO / identity"),
    ("Firebase Auth",     ["identitytoolkit.googleapis", "firebaseapp.com"],   "auth",        "Auth / identity (Firebase)"),
    ("Cognito",           ["cognito-idp", "amazoncognito.com"],                "auth",        "Auth / identity (AWS Cognito)"),
    # fraud / device
    ("FingerprintJS",     ["fpnpmcdn.net", "fingerprintjs", "fpjs.io",
                           "fingerprint-id", "api.fpjs"],                      "fraud",       "Device fingerprinting / bot & fraud signals"),
    ("hCaptcha",          ["hcaptcha.com"],                                    "fraud",       "CAPTCHA / bot mitigation"),
    ("reCAPTCHA",         ["recaptcha", "gstatic.com/recaptcha"],              "fraud",       "CAPTCHA / bot mitigation"),
    ("Cloudflare Turnstile", ["challenges.cloudflare.com", "turnstile"],       "fraud",       "CAPTCHA / bot mitigation"),
    # observability
    ("Sentry",            ["sentry.io", "sentry-cdn", "@sentry", "ingest.sentry"], "observability", "Error tracking"),
    ("Datadog",           ["datadoghq", "browser-intake-datadoghq", "dd-api-key"], "observability", "RUM / logs / monitoring"),
    ("LogRocket",         ["logrocket", "lr-ingest"],                          "observability", "Session replay / monitoring"),
    ("New Relic",         ["newrelic", "nr-data.net"],                         "observability", "APM / monitoring"),
    ("Bugsnag",           ["bugsnag"],                                         "observability", "Error tracking"),
    # product analytics
    ("Google Analytics",  ["google-analytics.com", "googletagmanager",
                           "gtag/js", "/gtag", "g-tag"],                       "analytics",   "Web analytics / tag manager"),
    ("Segment",           ["segment.com", "segment.io", "cdn.segment"],        "analytics",   "Analytics pipeline"),
    ("Amplitude",         ["amplitude.com", "amplitude"],                      "analytics",   "Product analytics"),
    ("Mixpanel",          ["mixpanel"],                                        "analytics",   "Product analytics"),
    ("PostHog",           ["posthog"],                                         "analytics",   "Product analytics"),
    ("Heap",              ["heap.io", "heapanalytics"],                        "analytics",   "Product analytics"),
    ("Hotjar",            ["hotjar"],                                          "analytics",   "Heatmaps / session"),
    # feature flags
    ("LaunchDarkly",      ["launchdarkly", "ldclient"],                        "flags",       "Feature flags"),
    ("Statsig",           ["statsig"],                                         "flags",       "Feature flags / experiments"),
    ("Optimizely",        ["optimizely"],                                      "flags",       "Experiments / flags"),
    # onboarding / support / comms
    ("Userflow",          ["userflow.com", "userflow"],                        "onboarding",  "In-app onboarding / tours"),
    ("Appcues",           ["appcues"],                                         "onboarding",  "In-app onboarding"),
    ("Pendo",             ["pendo.io"],                                        "onboarding",  "Product adoption / onboarding"),
    ("Intercom",          ["intercom.io", "intercomcdn", "widget.intercom"],   "support",     "Support chat"),
    ("Zendesk",           ["zendesk", "zdassets"],                             "support",     "Support"),
    ("Statuspage",        ["statuspage.io"],                                   "status",      "Public status page (Atlassian)"),
    # payments / billing
    ("Stripe",            ["stripe.com", "js.stripe", "stripe"],               "payments",    "Payments / billing"),
    ("Paddle",            ["paddle.com"],                                      "payments",    "Payments / billing"),
    ("Chargebee",         ["chargebee"],                                       "payments",    "Subscription billing"),
    # storage / cdn / cloud
    ("DigitalOcean Spaces", ["digitaloceanspaces.com"],                        "storage",     "Object storage / CDN"),
    ("AWS S3",            ["s3.amazonaws.com", ".s3.", "amazonaws.com/s3"],     "storage",     "Object storage"),
    ("Google Cloud Storage", ["storage.googleapis.com"],                       "storage",     "Object storage"),
    ("Cloudflare R2",     ["r2.cloudflarestorage", "r2.dev"],                   "storage",     "Object storage"),
    ("Cloudfront",        ["cloudfront.net"],                                   "cdn",         "CDN"),
    ("Cloudinary",        ["cloudinary"],                                       "cdn",         "Media CDN / transforms"),
    ("Vercel",            ["vercel.app", "vercel.com", "x-vercel"],             "hosting",     "Frontend hosting"),
    ("Netlify",           ["netlify.app", "netlify.com"],                      "hosting",     "Frontend hosting"),
    ("Cloudflare",        ["cloudflare", "__cf_bm", "cf-ray", "cdn-cgi"],       "edge",        "CDN / edge / bot mgmt"),
    # data / search / backend platforms
    ("Supabase",          ["supabase.co", "supabase"],                        "backend",     "Backend-as-a-service (Postgres)"),
    ("Firebase",          ["firebaseio.com", "firestore.googleapis"],          "backend",     "Backend-as-a-service"),
    ("Algolia",           ["algolia.net", "algolia"],                          "search",      "Hosted search"),
    ("Hasura",            ["hasura"],                                          "backend",     "GraphQL engine"),
    # integrations / unified APIs (product connectors)
    ("Kombo.dev",         ["kombo.dev", "connect.kombo"],                      "integration", "Unified ATS/HRIS API"),
    ("Merge.dev",         ["merge.dev", "merge.link"],                         "integration", "Unified API (HRIS/ATS/accounting)"),
    ("Finch",             ["tryfinch", "finch.com"],                           "integration", "Unified payroll/HRIS API"),
    ("Plaid",             ["plaid.com"],                                       "integration", "Bank / fintech data"),
    ("Nango",             ["nango.dev"],                                       "integration", "OAuth integration platform"),
    ("BrightHire",        ["brighthire"],                                      "integration", "Interview intelligence / recordings"),
    ("Recall.ai",         ["recall.ai", "recall-participants", "interview-bot"],"integration", "Meeting bots"),
    ("Crunchbase",        ["crunchbase"],                                      "integration", "Company enrichment data"),
    ("Greenhouse",        ["greenhouse.io"],                                   "integration", "ATS (often via a unified API)"),
    ("Lever",             ["lever.co"],                                        "integration", "ATS (often via a unified API)"),
    ("Ashby",             ["ashbyhq"],                                         "integration", "ATS (often via a unified API)"),
    ("Workday",           ["workday.com", "myworkday"],                        "integration", "HRIS/ATS"),
    ("Google Maps",       ["maps.googleapis", "maps.google"],                  "integration", "Maps / geocoding"),
    ("Twilio",            ["twilio.com"],                                      "integration", "Comms (SMS/voice)"),
    ("SendGrid",          ["sendgrid"],                                        "integration", "Transactional email"),
]

# Framework / build-tool fingerprints, matched against HTML + JS text.
FRAMEWORKS = [
    ("Next.js",     [r"/_next/static/", r"__NEXT_DATA__", r"self\.__next_f", r"next/dist"]),
    ("Vite",        [r"/assets/index-[A-Za-z0-9_-]{6,}\.js", r"__vite__mapDeps", r"import\.meta\.env"]),
    ("Create React App", [r"/static/js/main\.[0-9a-f]{8}\.js"]),
    ("Nuxt",        [r"/_nuxt/", r"__NUXT__"]),
    ("SvelteKit",   [r"/_app/immutable/", r"__sveltekit"]),
    ("Angular",     [r"ng-version=", r"runtime\.[0-9a-f]+\.js", r"polyfills\.[0-9a-f]+\.js"]),
    ("Vue",         [r"__VUE__", r"vue-router"]),
    ("Remix",       [r"__remixContext", r"/build/_shared/"]),
    ("Gatsby",      [r"___gatsby", r"/page-data/"]),
    ("Webpack",     [r"webpackJsonp", r"__webpack_require__", r"webpack-[0-9a-f]+\.js"]),
    ("Redux",       [r"@@redux", r"redux-toolkit", r"createSlice"]),
    ("React",       [r"react-dom", r"React\.createElement", r"jsxRuntime", r"__REACT_DEVTOOLS"]),
    ("Tailwind",    [r"tailwind", r"tw-merge", r"class-variance-authority"]),
    ("Emotion",     [r"@emotion", r"css-[0-9a-z]{6,}"]),
    ("Lingui",      [r"@lingui", r"/lingui"]),
]

ctx = ssl.create_default_context()

def fetch(url, method="GET", timeout=25, want_body=True, max_bytes=30_000_000):
    """Return (status, headers_dict, final_url, body_bytes|None, error|None)."""
    req = request.Request(url, method=method, headers={
        "User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"})
    try:
        with request.urlopen(req, timeout=timeout, context=ctx) as r:  # type: HTTPResponse
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            body = r.read(max_bytes) if want_body else None
            return r.status, hdrs, r.geturl(), body, None
    except error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in (e.headers or {}).items()}
        try:
            body = e.read(max_bytes) if want_body else None
        except Exception:
            body = None
        return e.code, hdrs, url, body, None
    except Exception as e:
        return None, {}, url, None, f"{type(e).__name__}: {e}"

def text(b):
    return b.decode("utf-8", "ignore") if b else ""

# ---- HTML asset discovery -------------------------------------------------
SRC_RE   = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)
LINK_RE  = re.compile(r'<link[^>]+href=["\']([^"\']+)["\']', re.I)
INLINE_HOST_RE = re.compile(r'https?://([a-zA-Z0-9._-]+)')

def discover_from_html(html, origin):
    scripts, styles, cross = [], [], set()
    for m in SRC_RE.finditer(html):
        u = urljoin(origin, m.group(1))
        if urlparse(u).netloc == urlparse(origin).netloc and u.split("?")[0].endswith(".js"):
            scripts.append(u)
        elif urlparse(u).netloc != urlparse(origin).netloc:
            cross.add(urlparse(u).netloc)
    for m in LINK_RE.finditer(html):
        u = urljoin(origin, m.group(1))
        base = u.split("?")[0]
        if urlparse(u).netloc == urlparse(origin).netloc and base.endswith(".js"):
            scripts.append(u)   # modulepreload/preload as script
        elif base.endswith(".css") and urlparse(u).netloc == urlparse(origin).netloc:
            styles.append(u)
    return list(dict.fromkeys(scripts)), list(dict.fromkeys(styles)), cross

# Additional chunk references discovered *inside* JS (bounded recursive crawl).
CHUNK_RE = re.compile(r'["\'`]((?:/|\./)?(?:assets|static|_next|_nuxt|build|chunks)/[A-Za-z0-9._/-]+?\.js)["\'`]')

def discover_from_js(js, origin, base_url):
    out = set()
    for m in CHUNK_RE.finditer(js):
        u = urljoin(base_url, m.group(1))
        if urlparse(u).netloc == urlparse(origin).netloc:
            out.add(u.split("?")[0])
    return out

# ---- extraction -----------------------------------------------------------
API_RE = re.compile(r'["\'`](/(?:api|rest|v[0-9]|graphql|gql|internal|webhooks?)/[A-Za-z0-9_${}./:-]*)')
URL_RE = re.compile(r'https?://[a-zA-Z0-9._-]+\.[a-zA-Z]{2,}(?:/[A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]*)?')
HOST_RE = re.compile(r'https?://([a-zA-Z0-9._-]+\.[a-zA-Z]{2,})')
SENTRY_DSN_RE = re.compile(r'https://[a-f0-9]+@[a-z0-9.]+\.ingest[a-z.]*\.sentry\.io/\d+')
WORKOS_CLIENT_RE = re.compile(r'client_[0-9A-Z]{20,}')
VITE_ENV_RE = re.compile(r'\b(VITE_[A-Z0-9_]+|NEXT_PUBLIC_[A-Z0-9_]+)\b')
GA_RE = re.compile(r'\b(G-[A-Z0-9]{8,}|GTM-[A-Z0-9]+|UA-\d+-\d+)\b')

API_HOST_RE = re.compile(r'(?:^|[.-])(api|apis|service|svc|gateway|graph|hook|proxy|'
                         r'identification|backend|rest|gql|graphql|edge|core)(?:[.-]|$)')
WEB_LABELS = {"www", "app", "support", "help", "docs", "doc", "blog", "careers", "career",
              "join", "status", "mail", "cdn", "assets", "static", "img", "images", "media",
              "download", "downloads", "account", "accounts", "login", "dashboard", "home",
              "marketing", "go", "get", "info", "news", "community", "learn", "about"}

# ---- alias resolution -----------------------------------------------------
# Apps hide their API hosts behind a named base: a variable or function bound to
# a subdomain URL (often `env.X || "https://host"`), then used as `${base()}/p`,
# `${base}/p`, or `base()+"/p"`. We resolve that generically in two passes:
#   1. build a name -> host map from any binding that yields a URL literal,
#   2. attribute the paths appended to each such name back to its host.
# This is deliberately pattern-shaped, not GetReal-specific.

_URL_LIT = r'["\'`](https?://[a-zA-Z0-9.-]+[^"\'`]*)["\'`]'
ALIAS_DEFS = [
    # function NAME(){ ... "https://host" ... }   (return env||"host" or return "host")
    re.compile(r'function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{[^{}]{0,160}?' + _URL_LIT),
    # NAME = () => ... "host"   |   NAME = function(){... "host"}   |   NAME = env||"host"
    re.compile(r'\b([A-Za-z_$][\w$]*)\s*=\s*(?:\([^)]*\)\s*=>|function\s*\([^)]*\)\s*\{)?[^;,{}\n]{0,120}?' + _URL_LIT),
    # NAME: ... "host"   (config-object property)
    re.compile(r'([A-Za-z_$][\w$]*)\s*:\s*[^,{}\n]{0,120}?' + _URL_LIT),
]

def _clean_api_path(p):
    p = re.split(r'[`"\';,)]', p, 1)[0]        # stop at end of the string/expr
    p = re.sub(r'\$\{[^}]*\}', '{id}', p)       # ${var} interpolation -> {id}
    p = re.sub(r'\$\{[^}]*$', '{id}', p)        # dangling interpolation
    p = re.sub(r'<[^>]+>', '{id}', p)           # <version>-style placeholders -> {id}
    p = p.split('?')[0].rstrip('/ ')
    m = re.match(r'(/[A-Za-z0-9_{}./~:-]*)', p)
    return m.group(1) if m else ''

def resolve_alias_paths(text, apex):
    """Return {host: set(paths)} for own-apex hosts aliased then used with paths."""
    name2host = {}
    for rx in ALIAS_DEFS:
        for m in rx.finditer(text):
            name, url = m.group(1), m.group(2)
            h = urlparse(url if "//" in url else "//" + url).netloc.lower()
            if not h or not (h == apex or h.endswith("." + apex)):
                continue
            if name in name2host and name2host[name] != h:
                name2host[name] = None          # ambiguous name -> disable
            elif name not in name2host:
                name2host[name] = h
    out = {}
    for name, h in name2host.items():
        if not h:
            continue
        n = re.escape(name)
        pats = [
            r'\$\{[^{}]{0,40}?\b' + n + r'\(\)\}([^`"\';,)]{1,120})',   # ${base()}/p
            r'\$\{[^{}]{0,40}?\b' + n + r'\}([^`"\';,)]{1,120})',        # ${base}/p
            r'(?<![\w$.])' + n + r'\(\)\s*\+\s*["\'`](/[^"\'`]{1,120})',  # base()+"/p"
            r'(?<![\w$.])' + n + r'\s*\+\s*["\'`](/[^"\'`]{1,120})',      # base+"/p"
        ]
        for pat in pats:
            for m in re.finditer(pat, text):
                p = _clean_api_path(m.group(1))
                if len(p) > 1 and "/" in p[1:] or (len(p) > 2):
                    if p and p != "/":
                        out.setdefault(h, set()).add(p)
    return out

def compute_api_surface(blob, hostnames, host, csp_directives, alias_paths=None):
    """Attribute API hosts + literal paths from the already-downloaded JS only.
    No probing - purely what the bundle already contains."""
    apex = ".".join(host.split(".")[-2:]) if host else ""
    own = sorted(h for h in hostnames if apex and (h == apex or h.endswith("." + apex)))
    self_label = host.split(".")[0]

    def label(h):
        if h == apex:
            return ""
        return h[:-(len(apex) + 1)] if h.endswith("." + apex) else h

    # literal absolute API URLs that appear in the bundle, bucketed by host
    attr = {h: set() for h in own}
    for m in re.finditer(r'https?://([a-zA-Z0-9.-]+)(/[A-Za-z0-9_${}./:-]*)', blob):
        h, p = m.group(1).lower(), m.group(2)
        if h in attr and len(p) > 1 and re.search(r'/(api|v[0-9]+|graphql|rest)(/|$)', p):
            attr[h].add(p)
    # alias-resolved paths (a var/function bound to a host, then used with a path)
    if alias_paths:
        for h, paths in alias_paths.items():
            if h not in attr:
                attr[h] = set()
                own.append(h)
            attr[h] |= {re.sub(r'\$\{[^}]*\}', '{id}', p) for p in paths}
    own = sorted(set(own))

    def classify(h):
        lab = label(h)
        if attr[h]:
            return True, "literal API URLs in bundle"
        if lab and API_HOST_RE.search(lab):
            return True, "host name"
        if lab and lab not in WEB_LABELS and lab != self_label:
            return True, "referenced service host"
        return False, ""

    hosts = {}
    for h in own:
        ok, why = classify(h)
        hosts[h] = {"is_api": ok, "reason": why, "paths": sorted(attr[h])}

    # primary backend: prefer a connect-src own host named like a gateway/proxy/api
    conn = [v.strip().strip("'").replace("wss://", "").replace("https://", "")
            .replace("http://", "").split("/")[0] for v in csp_directives.get("connect-src", [])]
    conn_own = [c for c in conn if c in own and label(c) not in WEB_LABELS and label(c) != self_label]

    def score(h):
        lab = label(h)
        if re.search(r'proxy|gateway|backend', lab):
            return 3
        if re.search(r'(?:^|[.-])api(?:[.-]|$)', lab):
            return 2
        return 1
    # Only name a backend when the CSP actually declares it (a real signal).
    # A wildcard connect-src (or none) tells us nothing, so we don't guess.
    backend = sorted(conn_own, key=lambda h: (-score(h), h))[0] if conn_own else None
    return {"apex": apex, "backend": backend, "hosts": hosts}

def parse_csp(csp):
    directives = {}
    if not csp:
        return directives
    for part in csp.split(";"):
        part = part.strip()
        if not part:
            continue
        toks = part.split()
        name, vals = toks[0], toks[1:]
        hosts = [v for v in vals if ("." in v or v.startswith("'") is False) and v not in ("'self'", "'none'")]
        directives[name] = vals
    return directives

def match_vendors(blob, hosts, csp_hosts):
    hay = (blob + " " + " ".join(hosts) + " " + " ".join(csp_hosts)).lower()
    found = []
    for name, pats, cat, note in VENDORS:
        hits = [p for p in pats if p.lower() in hay]
        if hits:
            found.append({"name": name, "category": cat, "note": note, "matched": hits})
    return found

def match_frameworks(blob):
    out = []
    for name, pats in FRAMEWORKS:
        for p in pats:
            if re.search(p, blob):
                out.append(name)
                break
    return out

# ---- host probing ---------------------------------------------------------
def probe_host(url):
    """Best-effort tech fingerprint of a backend/auth host via GET + OPTIONS."""
    result = {"url": url}
    st, h, final, body, err = fetch(url, method="GET", timeout=15, want_body=True, max_bytes=4000)
    if err:
        result["error"] = err
        return result
    result["status"] = st
    result["final_url"] = final
    for k in ("server", "x-powered-by", "content-type", "x-vercel-id", "x-matched-path",
              "www-authenticate", "cf-ray", "strict-transport-security", "x-frame-options"):
        if k in h:
            result[k] = h[k]
    bt = text(body)
    if bt.strip().startswith("{") and ("problem" in (h.get("content-type","")) or '"type"' in bt):
        result["body_snippet"] = bt[:300]
    st2, h2, _, _, _ = fetch(url, method="OPTIONS", timeout=12, want_body=False)
    cors = {k: v for k, v in h2.items() if k.startswith("access-control")}
    if cors:
        result["cors"] = cors
    return result

def primary_hosts(csp_directives, origin_host):
    """Pick likely backend + auth hosts from connect-src / the redirect chain."""
    conn = csp_directives.get("connect-src", [])
    hosts = []
    for v in conn:
        v = v.strip().strip("'")
        if "." in v and not v.startswith("wss") and "sentry" not in v and "userflow" not in v \
           and "datadog" not in v and "google" not in v:
            h = v.replace("wss://", "").replace("https://", "").replace("http://", "").split("/")[0]
            if h and h != origin_host and "*" not in h:
                hosts.append(h)
    return list(dict.fromkeys(hosts))[:4]

# ---- diff against previous run --------------------------------------------
def find_prev_run(out_dir):
    """Most recent earlier run for the same host (sibling timestamp dir)."""
    host_dir = os.path.dirname(out_dir.rstrip("/"))
    cur = os.path.basename(out_dir.rstrip("/"))
    try:
        sibs = sorted(d for d in os.listdir(host_dir)
                      if d < cur and os.path.isfile(os.path.join(host_dir, d, "report.json")))
    except FileNotFoundError:
        return None
    return os.path.join(host_dir, sibs[-1]) if sibs else None

def _as_set(r, key):
    v = r.get(key)
    return set(v.keys()) if isinstance(v, dict) else set(v or [])

def diff_reports(prev, cur):
    d = {}
    for key, label in (("api_endpoints", "endpoints"), ("hostnames", "hosts")):
        p, c = _as_set(prev, key), _as_set(cur, key)
        d[label] = {"added": sorted(c - p), "removed": sorted(p - c)}
    pv = {v["name"] for v in prev.get("vendors", [])}
    cv = {v["name"] for v in cur.get("vendors", [])}
    d["vendors"] = {"added": sorted(cv - pv), "removed": sorted(pv - cv)}
    pc, cc = prev.get("config_tokens", {}), cur.get("config_tokens", {})
    d["config_keys"] = {"added": sorted(set(cc) - set(pc)), "removed": sorted(set(pc) - set(cc))}
    return d

def _diff_has_changes(d):
    return any(v["added"] or v["removed"] for v in d.values())

# ---- main -----------------------------------------------------------------
def normalize(u):
    if not re.match(r'^https?://', u):
        u = "https://" + u
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc}", p.netloc

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-files", type=int, default=120)
    ap.add_argument("--max-mb", type=int, default=150)
    ap.add_argument("--no-probe", action="store_true")
    ap.add_argument("--save-raw", action="store_true", help="also write downloaded JS to raw/")
    args = ap.parse_args()

    origin, origin_host = normalize(args.url)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = args.out or os.path.expanduser(f"~/.claude/data/built-with/{origin_host}/{stamp}")
    os.makedirs(out, exist_ok=True)
    if args.save_raw:
        os.makedirs(os.path.join(out, "raw"), exist_ok=True)

    print(f"[*] target: {origin}")
    report = {
        "target": origin, "host": origin_host,
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "root": {}, "assets": {}, "csp": {}, "headers_of_interest": {},
        "api_endpoints": [], "hostnames": {}, "vendors": [], "other_hosts": [],
        "frameworks": [], "config_tokens": {}, "host_probes": [], "notes": [],
    }

    # 1) root
    st, hdrs, final, body, err = fetch(origin, timeout=25)
    if err:
        report["root"] = {"error": err}
        _write(out, report)
        print(f"[!] could not fetch root: {err}")
        return
    html = text(body)
    report["root"] = {"status": st, "final_url": final, "bytes": len(body or b"")}
    for k in ("server", "content-security-policy", "x-powered-by", "x-vercel-id",
              "x-matched-path", "strict-transport-security", "x-frame-options",
              "content-type", "set-cookie", "x-content-type-options"):
        if k in hdrs:
            report["headers_of_interest"][k] = hdrs[k]

    csp_directives = parse_csp(hdrs.get("content-security-policy", ""))
    report["csp"] = csp_directives
    csp_hosts = sorted({h.strip().strip("'").replace("wss://", "").replace("https://", "")
                        .replace("http://", "").split("/")[0]
                        for vals in csp_directives.values() for h in vals
                        if "." in h and "'" not in h.strip("'")[:1]})

    # 2) discover + download assets (bounded BFS)
    scripts, styles, cross = discover_from_html(html, origin)
    report["assets"]["stylesheets"] = styles
    report["assets"]["cross_origin_scripts"] = sorted(cross)
    seen, queue, downloaded = set(), list(scripts), []
    total = 0
    blob_parts = [html]
    while queue and len(downloaded) < args.max_files and total < args.max_mb * 1_000_000:
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        # never truncate a JS file - alias/host maps often live past the 8 MB
        # mark in a single huge chunk, and cutting it loses the attribution
        s2, _, _, b2, e2 = fetch(u, timeout=45, max_bytes=64_000_000)
        if e2 or not b2:
            continue
        js = text(b2)
        total += len(b2)
        downloaded.append({"url": u, "bytes": len(b2)})
        blob_parts.append(js)
        if args.save_raw:
            fn = re.sub(r'[^A-Za-z0-9._-]', '_', u.split("/")[-1])[:120] or "chunk.js"
            with open(os.path.join(out, "raw", fn), "w") as fh:
                fh.write(js)
        for nu in discover_from_js(js, origin, u):
            if nu not in seen and len(seen) + len(queue) < args.max_files * 3:
                queue.append(nu)
    report["assets"]["downloaded"] = downloaded
    report["assets"]["downloaded_count"] = len(downloaded)
    report["assets"]["downloaded_bytes"] = total
    blob = "\n".join(blob_parts)

    # 3) extract
    apis = sorted({m.group(1) for m in API_RE.finditer(blob)})
    report["api_endpoints"] = apis
    hosts_tally = {}
    for m in HOST_RE.finditer(blob):
        h = m.group(1).lower()
        hosts_tally[h] = hosts_tally.get(h, 0) + 1
    real = {h: c for h, c in hosts_tally.items() if h not in NOISE_HOSTS}
    report["hostnames"] = dict(sorted(real.items(), key=lambda kv: -kv[1]))
    report["other_hosts"] = sorted(h for h in hosts_tally if h in NOISE_HOSTS)

    report["vendors"] = match_vendors(blob, list(real.keys()), csp_hosts)
    report["frameworks"] = match_frameworks(blob)

    cfg = {}
    dsns = sorted(set(SENTRY_DSN_RE.findall(blob)))
    if dsns: cfg["sentry_dsn"] = dsns
    wc = sorted(set(WORKOS_CLIENT_RE.findall(blob)))
    if wc: cfg["workos_client_id"] = wc
    envs = sorted(set(VITE_ENV_RE.findall(blob)))
    if envs: cfg["build_env_vars"] = envs
    ga = sorted(set(GA_RE.findall(blob)))
    if ga: cfg["analytics_ids"] = ga
    # fingerprint public key sits right next to the fpnpmcdn loader template
    fp = re.search(r'`([A-Za-z0-9]{18,24})`\s*,\s*[A-Za-z_$]+\s*=\s*`https://[^`]+`\s*;?\s*async', blob)
    if "fpnpmcdn.net" in blob:
        keym = re.search(r'`([A-Za-z0-9]{18,24})`,[A-Za-z0-9_$]+=`https://[^`]*identification', blob)
        if keym: cfg["fingerprint_public_key"] = keym.group(1)
    report["config_tokens"] = cfg

    # attribute API/service hosts + paths from the bundle (no probing).
    # Resolve base-URL aliases per file so a var/function bound to a subdomain
    # can carry its appended paths back to that host.
    apex = ".".join(origin_host.split(".")[-2:])
    alias_paths = {}
    for part in blob_parts:
        for h, paths in resolve_alias_paths(part, apex).items():
            alias_paths.setdefault(h, set()).update(paths)
    report["api_surface"] = compute_api_surface(blob, real, origin_host, csp_directives, alias_paths)

    # 4) probe backend + auth hosts
    if not args.no_probe:
        targets = primary_hosts(csp_directives, origin_host)
        # add the auth host from the redirect chain / hostnames if present
        for h in list(real.keys()):
            if ("auth" in h or "login" in h) and h.endswith(tuple(origin_host.split(".")[-2:])) and h not in targets:
                targets.append(h)
        for h in targets[:5]:
            purl = "https://" + h + "/"
            # prefer a real API path when we found one, to elicit a 401/problem+json
            api_probe = next((a for a in apis if "${" not in a and a.count("/") >= 3), None)
            if "proxy" in h or "api" in h:
                purl = "https://" + h + (api_probe or "/")
            report["host_probes"].append(probe_host(purl))

    # 5) diff against the previous run for this host (one-off tool, but you want
    #    to know what changed since you last looked)
    prev_dir = find_prev_run(out)
    if prev_dir:
        try:
            prev = json.load(open(os.path.join(prev_dir, "report.json")))
            report["diff_against"] = os.path.basename(prev_dir)
            report["diff"] = diff_reports(prev, report)
        except Exception as e:
            report["diff_error"] = str(e)

    _write(out, report)
    _write_md(out, report)

    # ---- TLDR to screen ----
    print()
    print("  " + "=" * 60)
    print(f"  BUILT-WITH  ::  {report['host']}")
    print("  " + "=" * 60)
    print(f"  Frontend : {', '.join(report['frameworks'][:5]) or 'unknown'}")
    if report['headers_of_interest'].get('server'):
        print(f"  Hosting  : server={report['headers_of_interest']['server']}")
    print(f"  Vendors  : {len(report['vendors'])}  |  Endpoints: {len(apis)}  |  "
          f"Hosts: {len(real)}  |  JS files: {len(downloaded)}")
    if report['vendors']:
        names = ", ".join(v["name"] for v in report["vendors"])
        print(f"  Detected : {names}")
    if report.get("config_tokens"):
        print(f"  Tokens   : {', '.join(report['config_tokens'].keys())}")
    d = report.get("diff")
    if d and _diff_has_changes(d):
        print("  " + "-" * 60)
        print(f"  CHANGES since {report['diff_against']}:")
        for label in ("vendors", "endpoints", "hosts", "config_keys"):
            add, rem = d[label]["added"], d[label]["removed"]
            for item in add:
                print(f"    + [{label[:-1] if label.endswith('s') else label}] {item}")
            for item in rem:
                print(f"    - [{label[:-1] if label.endswith('s') else label}] {item}")
    elif d:
        print(f"  (no changes since {report['diff_against']})")
    elif prev_dir is None:
        print("  (first run for this host - future runs will diff against it)")
    print("  " + "=" * 60)
    print(f"  report: {out}/report.md")
    print(out)

def _write(out, report):
    with open(os.path.join(out, "report.json"), "w") as f:
        json.dump(report, f, indent=2)

def _cat_group(vendors, cats):
    return [v for v in vendors if v["category"] in cats]

def _write_md(out, r):
    L = []
    L.append(f"# Built-with: {r['host']}\n")
    L.append(f"- Target: {r['target']}")
    L.append(f"- Captured (UTC): {r['captured_utc']}")
    root = r.get("root", {})
    L.append(f"- Root: HTTP {root.get('status')} -> {root.get('final_url')}")
    hoi = r.get("headers_of_interest", {})
    if hoi.get("server"): L.append(f"- Server header: `{hoi['server']}`")
    if hoi.get("x-powered-by"): L.append(f"- X-Powered-By: `{hoi['x-powered-by']}`")
    L.append(f"- JS files analyzed: {r['assets'].get('downloaded_count',0)} "
             f"({r['assets'].get('downloaded_bytes',0):,} bytes)\n")

    L.append("## Frameworks / build tooling")
    L.append(", ".join(r["frameworks"]) or "_none detected_")
    L.append("")

    L.append("## Vendors detected (by category)")
    order = [("auth","Auth / identity"),("fraud","Fraud / bot / device"),
             ("integration","Product integrations"),("backend","Backend platforms"),
             ("storage","Storage"),("cdn","CDN"),("hosting","Hosting"),("edge","Edge / security"),
             ("payments","Payments"),("search","Search"),
             ("observability","Observability"),("analytics","Analytics"),("flags","Feature flags"),
             ("onboarding","Onboarding"),("support","Support"),("status","Status")]
    for cat, label in order:
        vs = _cat_group(r["vendors"], [cat])
        if vs:
            L.append(f"**{label}**")
            for v in vs:
                L.append(f"- {v['name']} - {v['note']} (matched: {', '.join(v['matched'][:3])})")
            L.append("")

    cfg = r.get("config_tokens", {})
    if cfg:
        L.append("## Public config tokens (browser-exposed)")
        for k, v in cfg.items():
            L.append(f"- {k}: `{v if not isinstance(v, list) else ', '.join(v)}`")
        L.append("")

    csp = r.get("csp", {})
    if csp:
        L.append("## CSP allow-lists (map of the stack)")
        for d in ("connect-src", "script-src", "frame-src", "img-src", "media-src"):
            if d in csp:
                L.append(f"- **{d}**: {' '.join(csp[d])}")
        L.append("")

    probes = r.get("host_probes", [])
    if probes:
        L.append("## Backend / auth host probes")
        for p in probes:
            L.append(f"- `{p.get('url')}` -> HTTP {p.get('status')} "
                     f"{('server='+p['server']) if p.get('server') else ''} "
                     f"{('| '+p['content-type']) if p.get('content-type') else ''}")
            if p.get("body_snippet"):
                L.append(f"  - body: `{p['body_snippet'][:180]}`")
            if p.get("cors"):
                L.append(f"  - CORS: {json.dumps(p['cors'])}")
        L.append("")

    d = r.get("diff")
    if d is not None:
        L.append(f"## Changes since last run ({r.get('diff_against','-')})")
        if _diff_has_changes(d):
            for label in ("vendors", "endpoints", "hosts", "config_keys"):
                for item in d[label]["added"]:
                    L.append(f"- **+ new** ({label}): `{item}`")
                for item in d[label]["removed"]:
                    L.append(f"- **- gone** ({label}): `{item}`")
        else:
            L.append("_No changes since the previous run._")
        L.append("")

    apis = r.get("api_endpoints", [])
    L.append(f"## API endpoints ({len(apis)})")
    for a in apis:
        L.append(f"- `{a}`")
    L.append("")

    hosts = r.get("hostnames", {})
    L.append(f"## Referenced hosts ({len(hosts)})")
    for h, c in list(hosts.items())[:60]:
        L.append(f"- {h} (x{c})")
    L.append("")

    with open(os.path.join(out, "report.md"), "w") as f:
        f.write("\n".join(L))

if __name__ == "__main__":
    main()
