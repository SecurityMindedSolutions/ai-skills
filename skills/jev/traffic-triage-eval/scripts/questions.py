"""Every constant a reviewer needs to see in one place: the questions Jev is
asked about each IP profile, the categories, and the rules that turn answers
into a verdict. Nothing else in this skill decides anything.

The state Jev sees is {"app": <paragraph about the site>, "window": <what
period the profile covers>, "profile": <profile.py output>}. Every count in
`profile` was computed in code; Jev is asked what the pattern means, never to
count or compare numbers. Questions name the state fields they are about
because Jev reads literally.
"""

MODEL = "jev-latest"

CATEGORIES = {
    "benign_user": "A person using a web browser or the product's own client, doing ordinary things: page loads with their assets, a sign-in with at most a retry or two, the occasional typo or 404.",
    "benign_bot": "A well-behaved automated client: a search-engine crawler, an uptime or health monitor, a link-preview fetcher, a feed reader, the operator's own scheduler, or a customer's scripted integration that calls the routes it is entitled to and gets successes.",
    "ai_agent": "An AI assistant or LLM-driven agent or crawler (GPTBot, ClaudeBot, PerplexityBot, an MCP client, a browsing agent). Not malicious by itself; reported separately so the operator can decide.",
    "background_scan": "Internet background noise: the same probes every host on the internet receives, sprayed at the server by raw IP or at software this site does not run (WordPress, PHP, .env files, old CVEs), even when a probe carries an exploit string. It shows no knowledge of this application: not its hostnames, not its routes, not its parameters.",
    "malicious": "Malicious scanning or an attack on this application: exploit payloads (injection, traversal, SSRF, JNDI, serialized objects) against routes that exist here, repeated sign-in or token attempts against its real auth endpoints, enumeration of its ids or tenants, persistent recon of its real routes on its real hostnames, or a scanning campaign that rotates through many identities to evade blocking.",
    "unclear": "Too little traffic or evidence to say.",
}

QUESTIONS = {
    "traffic_class": {
        "type": "choice",
        "instructions": (
            "Read `profile`, the code-computed summary of one client IP's requests to the "
            "site described in `app` during `window`. Which option best describes what "
            "that IP was doing? Judge from the pattern as a whole: the paths asked for and "
            "whether they exist on this site, the User-Agent, the pace, the response codes, "
            "and the WAF verdicts. Choose `unclear` only when the evidence is genuinely thin."
        ),
        "criteria": CATEGORIES,
    },
    "generic_probing": {
        "type": "noul",
        "instructions": (
            "Do the paths in `profile.paths`, `profile.probes` and `profile.paths.error_sample` "
            "ask for software, admin panels or files that the site in `app` does not run or "
            "serve, the way an internet-wide scanner tries the same list on every host?"
        ),
        "criteria": {
            "true": "Requests for WordPress, PHP admin tools, .env or .git files, Java consoles, other CMSs, backup archives or similar, on a site that `app` says is none of those.",
            "false": "Requests are for things this site actually serves, or there are no such probe paths.",
        },
    },
    "app_aware": {
        "type": "noul",
        "instructions": (
            "Do the requests in `profile.paths.top` target routes, endpoints or parameters "
            "that `app` says exist on this site, rather than a generic list any host might get?"
        ),
        "criteria": {
            "true": "Most requests are to real routes of this application: its API prefixes, its pages, its tenant or document URLs.",
            "false": "Requests are for generic paths, other software, or the root only; the client shows no knowledge of this application.",
        },
    },
    "exploit_payloads": {
        "type": "noul",
        "instructions": (
            "Does `profile.payloads` or `profile.queries.sample` show strings crafted to "
            "exploit a web application: SQL injection, cross-site scripting, path traversal, "
            "command or template injection, JNDI lookups, server-side request forgery targets, "
            "serialized objects, or scanner callback markers?"
        ),
        "criteria": {
            "true": "At least one request carries such a string in its path or query.",
            "false": "Paths and queries are ordinary parameters and values; `profile.payloads.summary` says none.",
        },
    },
    "credential_attack": {
        "type": "noul",
        "instructions": (
            "Does `profile` show repeated attempts against sign-in, password, MFA, token or "
            "registration endpoints (`profile.paths.auth_endpoint_requests`, the auth paths in "
            "`profile.paths.top`, and WAF rate-limit verdicts) beyond what one person signing in "
            "a few times would produce?"
        ),
        "criteria": {
            "true": "Dozens or more requests to authentication endpoints, many rejected with 401/403/429 or rate-limited by the WAF.",
            "false": "Few or no authentication requests, or a normal sign-in pattern of a handful of requests.",
        },
    },
    "enumeration": {
        "type": "noul",
        "instructions": (
            "Does `profile.paths.enumeration_templates` or `profile.paths.top` show the client "
            "iterating through ids, slugs, tenant names, usernames or file names to discover "
            "which ones exist on the site in `app`?"
        ),
        "criteria": {
            "true": "One URL template requested with many different id or name values, especially with mixed 200 and 404 results.",
            "false": "No template is filled with many different values; the variety of paths is ordinary navigation.",
        },
    },
    "automated": {
        "type": "noul",
        "instructions": (
            "Taking `profile.volume.summary`, `profile.user_agents`, "
            "`profile.paths.static_asset_fraction` and `profile.paths.requests_with_referer` "
            "together, is this traffic produced by software rather than by a person in a browser?"
        ),
        "criteria": {
            "true": "Machine pace or perfect regularity, a script, tool, crawler or empty User-Agent, no static assets or referers where a browser would load them.",
            "false": "Browser User-Agent, page loads followed by their assets, human pacing, or a client `app` describes as legitimate software.",
        },
    },
    "declared_bot": {
        "type": "noul",
        "instructions": (
            "Does the User-Agent in `profile.user_agents.top` honestly identify an automated "
            "client and who operates it (a named crawler, monitor, scheduler or fetcher)?"
        ),
        "criteria": {
            "true": "One consistent User-Agent that names a bot, crawler, monitor or service and usually its operator or a URL.",
            "false": "The User-Agent is a browser string, a bare HTTP library, a scanner tool, empty, or the IP rotates through many different bot names (`profile.code_signals.ua_spoofed_bots`), which means the names are fake.",
        },
    },
    "ai_operated": {
        "type": "noul",
        "instructions": (
            "Does `profile.user_agents` or the request pattern indicate an AI assistant, "
            "LLM crawler, or AI agent (for example GPTBot, ClaudeBot, PerplexityBot, "
            "an MCP client, a browsing or computer-use agent, or a class of `ai_agent`)?"
        ),
        "criteria": {
            "true": "One consistent User-Agent naming an AI company's crawler or agent, an AI tool, or an MCP client, and the requests read public content or use the API normally.",
            "false": "No AI-related User-Agent, or the IP rotates through many bot names (`profile.code_signals.ua_spoofed_bots`) while probing for files and exploits, which is a scanner wearing AI-crawler names, not an AI agent.",
        },
    },
    "monitoring": {
        "type": "noul",
        "instructions": (
            "Is this the pattern of a health check or uptime monitor: the same one or few "
            "paths (`profile.paths.top`, `profile.paths.health_endpoint_requests`) requested at "
            "a regular interval (`profile.volume.summary`) with consistent responses?"
        ),
        "criteria": {
            "true": "One to three fixed paths, regular timing, a monitoring or scheduler User-Agent or the operator's own service.",
            "false": "Varied paths, irregular timing, or a User-Agent that is not a monitor.",
        },
    },
    "wrong_host": {
        "type": "noul",
        "instructions": (
            "Does `profile.hosts.top` show requests addressed to a hostname that is not one of "
            "the hostnames `app` says this site serves, or to a raw IP address instead of a name?"
        ),
        "criteria": {
            "true": "At least one requested host is a bare IP address, a hostname `app` does not list, or a name that clearly belongs to something else.",
            "false": "Every requested host is one `app` names for this site.",
        },
    },
    "scanner_tool": {
        "type": "noul",
        "instructions": (
            "Is the client a vulnerability scanner or mass-scanning tool, judged from "
            "`profile.user_agents` (class scanner), `profile.probes`, `profile.payloads` and "
            "a high not-found rate in `profile.responses`?"
        ),
        "criteria": {
            "true": "A scanner User-Agent, or many probe families and payload types in a short window with mostly 404 responses.",
            "false": "Nothing suggests a scanning tool.",
        },
    },
    "threat_severity": {
        "type": "score",
        "instructions": (
            "Considering `profile` as a whole against the site in `app`, how much of a "
            "threat does this IP's activity represent to this application?"
        ),
        "criteria": [
            "None. Ordinary use, a declared bot, or a monitor.",
            "Nuisance. Background scanning for software this site does not run, including mass exploit attempts sprayed at the raw IP, all rejected; or an AI crawler reading public pages. No sign it knows this application.",
            "Concerning. Recon of endpoints that exist here on its real hostnames, repeated authentication attempts, WAF denials on real routes, enumeration of ids, or a scanning campaign rotating identities across this site's hosts, without a clear successful exploit.",
            "Active attack. Exploit payloads against real endpoints, credential attacks at volume, or enumeration that is returning successes.",
        ],
    },
}

# --- Composition rules (code decides; Jev's answers are inputs) ------------
SIGNAL_THRESHOLD = 0.5        # a noul at or above this is reported in the Signals column
CHOICE_MIN_CONFIDENCE = 0.45  # below this the category is reported as unclear + needs_review
# Attention (the `!!` rows) is severity-driven: a `malicious` verdict at
# nuisance severity is still listed and colored, but a human reads the
# attention rows first, so those are severity >= 2 with confidence, or a
# code floor rule that fired (payloads on real routes, credential attack).
ATTENTION_SEVERITY = 2.0
ATTENTION_SEVERITY_CONF = 0.3

# Floors code applies from its own facts before Jev's rules. A floor never
# lowers a Jev verdict, only raises it. Category order for "raise":
CATEGORY_ORDER = ["unclear", "benign_user", "benign_bot", "ai_agent", "background_scan", "malicious"]

# A payload family hit against a route Jev says exists here (app_aware) is a
# targeted attack whatever the choice said: one SQLi against /api/v1/... is
# not noise even if the other 500 requests were.
PAYLOAD_PLUS_APP_AWARE = 0.6
# credential_attack at this level plus WAF or auth-volume evidence AND app_aware
# at least CREDENTIAL_MIN_APP_AWARE: malicious floor. The app_aware gate
# keeps 404s on /login and /wp-login.php (endpoints that do not exist here)
# from reading as a credential attack.
CREDENTIAL_FLOOR = 0.7
CREDENTIAL_MIN_APP_AWARE = 0.5
# A scanner-class UA, probe paths, raw-IP host, or Jev's wrong_host at or above
# WRONG_HOST, with app_aware below this: background_scan floor.
BACKGROUND_MAX_APP_AWARE = 0.4
WRONG_HOST = 0.7
# Fewer requests than this, with no code signal, is `unclear`: one GET / says nothing.
MIN_REQUESTS_FOR_VERDICT = 3

# Jev context: 32k tokens for state plus the longest question, 64k total.
# Measured with limits.py on 2026-09-19: 32,653 total input tokens accepted,
# the next step (~40k) refused with HTTP 400 max_tokens_exceeded; the app
# paragraph plus these questions cost ~3,500 tokens, so a profile may go to
# ~28k. Category and severity did not move between 4k and 32k, so the budget
# below is about cost and keeping the state focused, not accuracy.
MAX_PROFILE_TOKENS = 6_000

USD_PER_MILLION_INPUT_TOKENS = 0.042
