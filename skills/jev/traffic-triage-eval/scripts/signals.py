"""Deterministic pattern checks: the things a regex finds better than any
model. Every pattern here is matched in code and reported to Jev as a named
fact in the profile (`ua_class`, `probe_paths`, `payload_hits`), so Jev
judges the meaning and never has to spot the string itself.

Lists are starting points. When a run shows a UA or path family that should
have matched, add it here, not in a question.
"""

from __future__ import annotations

import re
from urllib.parse import unquote_plus

# --- User-Agent classes ------------------------------------------------------
# Checked in this order; the first match wins. `ai_agent` sits before
# `crawler` because most AI crawlers also say "bot".
UA_CLASSES: list[tuple[str, re.Pattern]] = [
    ("scanner", re.compile(
        r"nuclei|sqlmap|nikto|masscan|zgrab|nmap|dirbuster|gobuster|ffuf|feroxbuster|wfuzz|"
        r"acunetix|nessus|openvas|burp|w3af|arachni|whatweb|wpscan|joomscan|"
        r"httpx|katana|projectdiscovery|expanse|paloaltonetworks|censys|shodan|"
        r"internetmeasurement|netsystemsresearch|stretchoid|binaryedge|leakix|"
        r"criminalip|driftnet|odin\.io|onyphe|fofa|zoomeye|"
        r"l9explore|l9tcpid|Hello,? world|\bgo-http-client\b|libwww-perl", re.I)),
    ("ai_agent", re.compile(
        r"GPTBot|ChatGPT-User|OAI-SearchBot|ClaudeBot|Claude-User|Claude-SearchBot|anthropic-ai|"
        r"PerplexityBot|Perplexity-User|Google-Extended|Applebot-Extended|"
        r"Bytespider|CCBot|cohere-ai|Diffbot|YouBot|Amazonbot|meta-externalagent|"
        r"MistralAI-User|DuckAssistBot|Timpibot|omgili|ImagesiftBot|PetalBot|"
        r"AI2Bot|Ai2Bot-Dolma|iaskspider|Kangaroo Bot|Webzio-Extended|"
        r"browser-use|\bOperator\b|computer-use|\bDevin\b|OpenAI|Anthropic|"
        r"\bmcp\b|mcp-client|model-context-protocol|langchain|llama-?index|crewai|autogpt", re.I)),
    ("monitor", re.compile(
        r"UptimeRobot|Pingdom|StatusCake|Site24x7|Datadog|NewRelic|GoogleStackdriverMonitoring|"
        r"Google-Cloud-Scheduler|Google-Cloud-Tasks|GoogleHC|kube-probe|ELB-HealthChecker|"
        r"Amazon-Route53-Health-Check|Better ?Uptime|Uptime-Kuma|checkly|Freshping|Hetrix|"
        r"OhDear|updown\.io|Cloudflare-Healthchecks|Cloudflare-Traffic-Manager|GoogleAssociationService|"
        r"Cloud-Scheduler|Zabbix|Nagios|Prometheus|Blackbox Exporter", re.I)),
    ("crawler", re.compile(
        r"Googlebot|bingbot|Slurp|DuckDuckBot|Baiduspider|YandexBot|Applebot|facebookexternalhit|"
        r"Twitterbot|LinkedInBot|Slackbot|Discordbot|WhatsApp|TelegramBot|Pinterest|"
        r"AhrefsBot|SemrushBot|MJ12bot|DotBot|PetalBot|SeznamBot|Sogou|Qwantify|"
        r"archive\.org_bot|ia_archiver|Google-InspectionTool|Google-Site-Verification|"
        r"AdsBot|Mediapartners|GoogleOther|Storebot|FeedFetcher|feedparser|Feedly|"
        r"\bbot\b|crawler|spider|\bfetch(er)?\b|preview|validator|linkcheck|lighthouse|"
        r"PageSpeed|Chrome-Lighthouse|GTmetrix|WebPageTest", re.I)),
    ("script", re.compile(
        r"python-requests|python-urllib|aiohttp|httpx/|\bcurl/|\bwget/|okhttp|Java/|"
        r"Apache-HttpClient|axios|node-fetch|undici|Go-http-client|Dart/|libcurl|"
        r"PostmanRuntime|insomnia|Scrapy|colly|reqwest|Faraday|RestSharp|\bPHP/|"
        r"Guzzle|lua-resty|Ruby|Typhoeus|Symfony|HTTPie|resty", re.I)),
    ("headless", re.compile(r"HeadlessChrome|PhantomJS|Puppeteer|Playwright|Selenium|Electron", re.I)),
    ("browser", re.compile(r"Mozilla/5\.0.*(Chrome|Safari|Firefox|Edg|OPR|Trident|Gecko)", re.I)),
]


def ua_class(ua: str | None) -> str:
    if not ua:
        return "empty"
    for name, pattern in UA_CLASSES:
        if pattern.search(ua):
            return name
    return "other"


# --- Path families that untargeted scanners look for --------------------------
# Each hit is reported by family so the profile reads "wordpress: 12, env_files:
# 3" rather than a wall of paths. A site that runs none of this software and
# gets these is background noise; a site that does run it is being probed.
PROBE_FAMILIES: dict[str, re.Pattern] = {
    "wordpress": re.compile(r"/(wp-login\.php|wp-admin|wp-content|wp-includes|xmlrpc\.php|wp-json|wlwmanifest\.xml)", re.I),
    "php_admin": re.compile(r"/(phpmyadmin|pma|myadmin|phpinfo\.php|adminer|mysql|dbadmin)\b|\.php(\?|$)", re.I),
    "env_files": re.compile(r"/\.env(\.|$)|/\.(git|svn|hg|DS_Store|htaccess|htpasswd|bash_history|aws|ssh|npmrc|docker)", re.I),
    "config_files": re.compile(r"/(config\.(json|yml|yaml|php|js)|web\.config|composer\.(json|lock)|package\.json|\.travis\.yml|appsettings\.json|settings\.py|secrets\.(json|yml)|credentials)(\?|$)", re.I),
    "backup_files": re.compile(r"\.(bak|old|orig|backup|sql|sql\.gz|tar\.gz|zip|rar|7z|swp)(\?|$)|/(backup|backups|dump|db_backup)", re.I),
    "java_actuator": re.compile(r"/(actuator|jolokia|env|beans|heapdump|console|manager/html|jmx-console|invoker|struts|solr|jenkins)\b", re.I),
    "cloud_metadata": re.compile(r"/latest/meta-data|/computeMetadata|/metadata/instance|169\.254\.169\.254", re.I),
    "api_docs": re.compile(r"/(swagger|openapi|api-docs|graphql|graphiql|\.well-known/openid-configuration|v2/api-docs)\b", re.I),
    # Anchored at the path start on purpose: an app's own /api/v1/.../dashboard
    # route is not a scanner target, /admin/ at the root is.
    "admin_panels": re.compile(r"^/(admin|administrator|manager|cpanel|webmail|login\.aspx|_admin|adminpanel)(/|$|\.)", re.I),
    "shells_exploits": re.compile(r"/(shell|cmd|c99|r57|eval|webshell|wso|alfa|filemanager)\.(php|jsp|asp|aspx)|/cgi-bin/|/boaform/|/HNAP1|/GponForm|/setup\.cgi|/tmUnblock|/vendor/phpunit|ThinkPHP|/owa/|/ecp/|/autodiscover/|/remote/login|/\+CSCOE\+|/global-protect|/dana-na/", re.I),
    "cms_other": re.compile(r"/(joomla|drupal|magento|typo3|umbraco|sitecore|craft|ghost|prestashop|opencart|bitrix|vtiger|roundcube|zimbra|nagios|zabbix|grafana|kibana|elastic|_cat/|_cluster/)\b", re.I),
    "node_js": re.compile(r"/(_next/|__nuxt/|\.next/|node_modules/|\.vscode/|\.idea/)", re.I),
}

# --- Payloads: exploit-shaped strings in the path or query ------------------
PAYLOAD_FAMILIES: dict[str, re.Pattern] = {
    "traversal": re.compile(r"\.\./|\.\.\\|%2e%2e|%252e|/etc/passwd|/proc/self|boot\.ini|win\.ini", re.I),
    "sqli": re.compile(r"(\bunion\b.{0,20}\bselect\b|\bsleep\(|benchmark\(|pg_sleep|waitfor\s+delay|'\s*or\s*'?\d|\bor\s+1\s*=\s*1|information_schema|@@version|xp_cmdshell|--\s*$|/\*!)", re.I),
    "xss": re.compile(r"<script|javascript:|onerror\s*=|onload\s*=|<img\b|<svg\b|alert\(|document\.cookie|String\.fromCharCode", re.I),
    "cmd_injection": re.compile(r"(;|\||`|\$\(|%0a|%0d)\s*(cat|ls|id|whoami|wget|curl|nc|bash|sh|powershell|cmd)\b|/bin/(ba)?sh|\bwhoami\b|\becho\b.{0,10}\$|\$\{IFS\}", re.I),
    "template_injection": re.compile(r"\{\{.{0,40}\}\}|\$\{.{0,40}\}|<%=|#\{.{0,40}\}", re.I),
    "log4shell_jndi": re.compile(r"\$\{jndi:|jndi:(ldap|rmi|dns)", re.I),
    "ssrf": re.compile(r"(url|uri|dest|redirect|next|target|src|href|callback|feed|host)=\s*(https?:)?//", re.I),
    "deserialization": re.compile(r"rO0AB|aced0005|O:\d+:\"|__proto__|constructor\[|\bprototype\b", re.I),
    "null_or_encoding": re.compile(r"%00|%c0%ae|%ef%bc%8f|\\x[0-9a-f]{2}|\\u00", re.I),
    "scanner_marker": re.compile(r"nuclei|acunetix|nikto|sqlmap|wpscan|\{\{interactsh|oast\.|burpcollab|dnslog|ceye\.io|canarytokens", re.I),
}

AUTH_PATH = re.compile(r"/(login|signin|sign-in|auth|oauth|token|password|mfa|totp|otp|2fa|register|signup|session|sso|saml)\b", re.I)
STATIC_EXT = re.compile(r"\.(js|mjs|css|map|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|avif|mp4|webm|json|txt|xml)$", re.I)
HEALTH_PATH = re.compile(r"/(health|healthz|ready|readyz|live|livez|ping|status|_ah/|heartbeat|up)$", re.I)
NUMERIC_SEGMENT = re.compile(r"/\d{1,12}(/|$)")
UUID_SEGMENT = re.compile(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(/|$)", re.I)


def probe_families(path: str) -> list[str]:
    return [name for name, pat in PROBE_FAMILIES.items() if pat.search(path)]


def payload_families(path: str, query: str | None) -> list[str]:
    text = unquote_plus(path + ("?" + query if query else ""))
    return [name for name, pat in PAYLOAD_FAMILIES.items() if pat.search(text) or pat.search(path + (query or ""))]


def is_static(path: str) -> bool:
    return bool(STATIC_EXT.search(path))


def is_auth(path: str) -> bool:
    return bool(AUTH_PATH.search(path))


def is_health(path: str) -> bool:
    return bool(HEALTH_PATH.search(path))


def is_raw_ip_host(host: str | None) -> bool:
    if not host:
        return False
    h = host.split(":")[0]
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", h) or (":" in h and re.match(r"^[0-9a-f:]+$", h, re.I)))


# Query keys whose value changes on every request by design; never enumeration.
CACHE_BUSTER_KEYS = {"cb", "_", "t", "ts", "v", "ver", "r", "rand", "random", "nocache", "cache", "timestamp",
                     "_t", "_ts", "cachebust", "bust", "hash", "nonce", "sid", "session", "state", "code", "token"}


def query_params(query: str | None) -> list[tuple[str, str]]:
    """(key, value) pairs of a raw query string; values decoded, keys as-is,
    cache-buster and one-time keys dropped so they cannot look like enumeration."""
    if not query:
        return []
    out = []
    for part in query.split("&"):
        key, _, value = part.partition("=")
        if key and key.lower() not in CACHE_BUSTER_KEYS:
            out.append((key, unquote_plus(value)))
    return out


HEX_SEGMENT = re.compile(r"/[0-9a-f]{16,}(?=/|$)", re.I)
HASHED_ASSET = re.compile(r"[-.][A-Za-z0-9_]{6,12}(?=\.[a-z0-9]+(\.map)?$)")
# a long segment with digits AND letters is an opaque id; a long word is a route name
LONG_TOKEN = re.compile(r"/(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{20,}(?=/|$)")


def path_template(path: str) -> str:
    """Collapse ids, hashes and long tokens so an application's routes roll
    up (`/api/v1/tenants/{slug}` stays, `/documents/{uuid}` collapses).
    Scanner wordlists do not compress this way, which is itself a signal."""
    p = enumeration_shape(path)
    p = HEX_SEGMENT.sub("/{hex}", p)
    p = LONG_TOKEN.sub("/{token}", p)
    return HASHED_ASSET.sub("-{hash}", p)


def path_directory(path: str, depth: int = 3) -> str:
    segs = [s for s in path.split("/") if s]
    if len(segs) <= depth:
        return path
    return "/" + "/".join(segs[:depth]) + "/*"


def path_extension(path: str) -> str:
    last = path.rsplit("/", 1)[-1]
    if "." not in last or last.startswith(".") and last.count(".") == 1:
        return "(none)" if not last.startswith(".") else last.lower()   # /.env -> ".env"
    return "." + last.rsplit(".", 1)[-1].lower()[:8]


def enumeration_shape(path: str) -> str:
    """Replace ids with placeholders so `/api/v1/tenants/123` and `/api/v1/tenants/124`
    collapse to one template; the count of distinct fills per template is the
    enumeration signal, computed in profile.py."""
    p = UUID_SEGMENT.sub("/{uuid}\\1", path)
    return NUMERIC_SEGMENT.sub("/{n}\\1", p)
