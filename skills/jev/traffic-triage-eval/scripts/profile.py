"""Turn a list of canonical events into one compact profile per IP.

Everything numeric or temporal is computed here, in code, because Jev does
not count and reads dates as text (docs.typesafe.ai/model-jaggedness). Each
number is also given as a named bucket ("bursty", "mostly 404") because Jev
judges words better than magnitudes. The profile is the whole `state` Jev
sees for that IP; anything not in it does not exist for the judgment.

`build_profile` returns a dict; `render` trims it to a token budget by
shrinking the sample lists, never the counts.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime

import signals as sig
from schema import parse_ts

# Sample-list sizes at budget. `render` halves these until the profile fits.
DEFAULT_SAMPLES = {"top_paths": 30, "error_paths": 15, "probe_paths": 15, "payload_paths": 15,
                   "queries": 10, "uas": 4, "hosts": 6,
                   "templates": 15, "directories": 12, "unmatched": 15}
MAX_PATH_CHARS = 160
MAX_QUERY_CHARS = 200
MAX_UA_CHARS = 140


def group_by_ip(events: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        groups[e["ip"]].append(e)
    return groups


def build_profile(ip: str, events: list[dict]) -> dict:
    events = sorted(events, key=lambda e: e["ts"])
    times = [parse_ts(e["ts"]) for e in events]
    n = len(events)
    span_s = (times[-1] - times[0]).total_seconds() if n > 1 else 0.0
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    minutes = Counter(t.strftime("%Y-%m-%dT%H:%M") for t in times)
    peak_rpm = max(minutes.values())
    # status is optional: WAF logs usually carry the verdict but not the backend's answer
    with_status = [e for e in events if e.get("status") is not None]
    status = Counter(e["status"] for e in with_status)
    classes = Counter(f"{e['status'] // 100}xx" if e["status"] else "0xx" for e in with_status)
    methods = Counter(e["method"] for e in events)
    hosts = Counter(e.get("host", "") for e in events)
    paths = Counter(e["path"] for e in events)
    uas = Counter(e.get("ua", "") for e in events)
    ua_classes = Counter(sig.ua_class(e.get("ua")) for e in events)
    waf = Counter(e.get("waf_action", "none") for e in events)
    waf_rules = Counter(e.get("waf_rule") for e in events if e.get("waf_action") in ("deny", "throttle", "challenge", "count"))
    waf_labels = Counter(lab for e in events for lab in e.get("waf_labels", []))
    attack_labels = Counter(lab for lab in waf_labels.elements() if sig.WAF_ATTACK_LABEL.search(lab))
    bot_labels = Counter(lab for lab in waf_labels.elements() if sig.WAF_BOT_LABEL.search(lab))
    reputation_labels = Counter(lab for lab in waf_labels.elements() if sig.WAF_REPUTATION_LABEL.search(lab))
    asns = Counter(e.get("asn") for e in events if e.get("asn") is not None)
    countries = Counter(e.get("country") for e in events if e.get("country"))
    ja3 = Counter(e.get("ja3") for e in events if e.get("ja3"))
    ja4 = Counter(e.get("ja4") for e in events if e.get("ja4"))

    probe_hits: Counter = Counter()
    probe_examples: dict[str, list[str]] = defaultdict(list)
    payload_hits: Counter = Counter()
    payload_examples: list[str] = []
    static = auth = health = raw_ip_host = referer = 0
    templates: dict[str, set] = defaultdict(set)
    error_paths: Counter = Counter()
    queries: Counter = Counter()
    tmpl: Counter = Counter()
    tmpl_fills: dict[str, set] = defaultdict(set)
    dirs: Counter = Counter()
    dir_leaves: dict[str, set] = defaultdict(set)
    exts: Counter = Counter()
    unmatched: Counter = Counter()      # paths no family, payload or static rule describes
    for e in events:
        path, query = e["path"], e.get("query")
        t = sig.path_template(path)
        tmpl[t] += 1
        tmpl_fills[t].add(path)
        d = sig.path_directory(path)
        dirs[d] += 1
        dir_leaves[d].add(path)
        exts[sig.path_extension(path)] += 1
        for fam in sig.probe_families(path):
            probe_hits[fam] += 1
            if len(probe_examples[fam]) < 3 and path not in probe_examples[fam]:
                probe_examples[fam].append(path)
        fams = sig.payload_families(path, query)
        for fam in fams:
            payload_hits[fam] += 1
        if fams and len(payload_examples) < 40:
            ex = _clip(path + ("?" + query if query else ""), MAX_QUERY_CHARS)
            if ex not in payload_examples:
                payload_examples.append(ex)
        described = bool(fams) or bool(sig.probe_families(path)) or sig.is_static(path) or sig.is_health(path)
        if not described:
            unmatched[path] += 1
        static += sig.is_static(path)
        # a 404 on /login is a probe for an endpoint that is not there, not a credential attempt
        auth += sig.is_auth(path) and e.get("status") not in (404, 405, 0)
        health += sig.is_health(path)
        raw_ip_host += sig.is_raw_ip_host(e.get("host"))
        referer += bool(e.get("referer"))
        templates[sig.enumeration_shape(path)].add(path)
        for key, value in sig.query_params(query):
            templates[f"{path}?{key}="].add(value)
        if e.get("status") in (404, 400, 403, 401, 405):
            error_paths[path] += 1
        if query:
            queries[_clip(query, MAX_QUERY_CHARS)] += 1

    enum_templates = sorted(((len(v), k) for k, v in templates.items() if len(v) >= 5), reverse=True)[:5]
    distinct_paths = len(paths)
    top_n = DEFAULT_SAMPLES["top_paths"]
    top_cov = sum(c for _, c in paths.most_common(top_n)) / n
    fam_described = n - sum(unmatched.values())
    compresses = len(tmpl) <= 0.8 * distinct_paths
    p404 = status.get(404, 0)
    err4 = classes.get("4xx", 0)
    ns = len(with_status)

    profile = {
        "ip": ip,
        "asn": asns.most_common(1)[0][0] if asns else None,
        "country": countries.most_common(1)[0][0] if countries else None,
        "tls_fingerprints": {"ja3_distinct": len(ja3), "ja4_distinct": len(ja4),
                             "ja4_top": [k for k, _ in ja4.most_common(2)]} if (ja3 or ja4) else None,
        "volume": {
            "requests": n,
            "first_seen": times[0].isoformat(timespec="seconds"),
            "last_seen": times[-1].isoformat(timespec="seconds"),
            "span_minutes": round(span_s / 60, 1),
            "active_minutes": len(minutes),
            "peak_requests_per_minute": peak_rpm,
            "median_gap_seconds": round(statistics.median(gaps), 2) if gaps else None,
            "fraction_of_gaps_under_1s": round(sum(g < 1 for g in gaps) / len(gaps), 2) if gaps else None,
            "summary": _volume_words(n, span_s, peak_rpm, gaps),
        },
        "hosts": {"distinct": len(hosts), "top": _top(hosts, DEFAULT_SAMPLES["hosts"]),
                  "requests_with_raw_ip_host": raw_ip_host},
        "methods": dict(methods.most_common()),
        "responses": {
            "requests_with_status": ns,
            "by_class": dict(classes),
            "top_statuses": dict(status.most_common(6)),
            "not_found_rate": round(p404 / ns, 2) if ns else None,
            "client_error_rate": round(err4 / ns, 2) if ns else None,
            "summary": _response_words(n, ns, p404, err4, classes.get("5xx", 0), classes.get("2xx", 0)),
        },
        "waf": {"actions": dict(waf), "rules_hit": _top(waf_rules, 5),
                "labels": _top(waf_labels, 10),
                "labels_summary": _label_words(attack_labels, bot_labels, reputation_labels, n),
                "summary": _waf_words(waf)},
        "user_agents": {
            "distinct": len(uas),
            "classes": dict(ua_classes.most_common()),
            "top": [{"ua": _clip(ua, MAX_UA_CHARS) or "(empty)", "requests": c, "class": sig.ua_class(ua)}
                    for ua, c in uas.most_common(DEFAULT_SAMPLES["uas"])],
        },
        "paths": {
            "distinct": distinct_paths,
            "distinct_per_request": round(distinct_paths / n, 2),
            "static_asset_fraction": round(static / n, 2),
            "auth_endpoint_requests": auth,
            "health_endpoint_requests": health,
            "requests_with_referer": referer,
            "enumeration_templates": [{"template": t, "distinct_values": c} for c, t in enum_templates],
            "coverage": _coverage_words(n, distinct_paths, top_n, top_cov, fam_described, len(tmpl), compresses),
            "top": [{"path": _clip(p, MAX_PATH_CHARS), "requests": c, "status": _status_for(events, p)}
                    for p, c in paths.most_common(top_n)],
            "error_sample": [_clip(p, MAX_PATH_CHARS) for p, _ in error_paths.most_common(DEFAULT_SAMPLES["error_paths"])],
            # route templates only when they actually roll paths up (an app, not a wordlist)
            "templates": [{"template": _clip(t, MAX_PATH_CHARS), "requests": c, "distinct_paths": len(tmpl_fills[t])}
                          for t, c in tmpl.most_common(DEFAULT_SAMPLES["templates"])] if compresses else [],
            # only directories that hold several distinct paths; single files are already in `top`
            "directories": [{"directory": _clip(d, MAX_PATH_CHARS), "requests": c, "distinct_paths": len(dir_leaves[d])}
                            for d, c in dirs.most_common() if len(dir_leaves[d]) >= 3][: DEFAULT_SAMPLES["directories"]],
            "extensions": dict(exts.most_common(8)),
            # the only raw paths worth a sample slot: the ones no family or rule described
            "unmatched_sample": [{"path": _clip(p, MAX_PATH_CHARS), "requests": c, "status": _status_for(events, p)}
                                 for p, c in unmatched.most_common(DEFAULT_SAMPLES["unmatched"])],
        },
        "probes": {
            "summary": _probe_words(probe_hits, n),
            "families": dict(probe_hits.most_common()),
            "examples": {fam: ex for fam, ex in probe_examples.items()},
        },
        "payloads": {
            "summary": _payload_words(payload_hits),
            "families": dict(payload_hits.most_common()),
            "examples": payload_examples[:DEFAULT_SAMPLES["payload_paths"]],
        },
        "queries": {"distinct": len(queries), "sample": [q for q, _ in queries.most_common(DEFAULT_SAMPLES["queries"])]},
    }
    # Facts code is sure about, for the report and for rule floors in classify.py.
    declared_bot_uas = sum(1 for ua in uas if sig.ua_class(ua) in ("crawler", "ai_agent", "monitor"))
    profile["code_signals"] = _code_signals(profile, ua_classes, probe_hits, payload_hits, waf, raw_ip_host, n, declared_bot_uas)
    if attack_labels:
        profile["code_signals"]["waf_attack_labels"] = (f"{sum(attack_labels.values())} requests carry WAF attack-signature labels: "
                                                         + ", ".join(f"{_short_label(k)}={v}" for k, v in attack_labels.most_common(4)))
    if reputation_labels:
        profile["code_signals"]["waf_reputation_labels"] = ("WAF IP-reputation or anonymizer labels: "
                                                             + ", ".join(_short_label(k) for k, _ in reputation_labels.most_common(3)))
    return profile


def _code_signals(p: dict, ua_classes: Counter, probes: Counter, payloads: Counter,
                  waf: Counter, raw_ip_host: int, n: int, declared_bot_uas: int = 0) -> dict[str, str]:
    out: dict[str, str] = {}
    lead = ua_classes.most_common(1)[0][0]
    if lead in ("scanner", "ai_agent", "monitor", "crawler", "script", "headless", "empty"):
        out[f"ua_{lead}"] = f"{ua_classes[lead]} of {n} requests carry a {lead}-class User-Agent"
    if len(p["user_agents"]["classes"]) >= 3 and p["user_agents"]["distinct"] >= 5:
        out["ua_rotation"] = f"{p['user_agents']['distinct']} distinct User-Agents across {len(p['user_agents']['classes'])} classes"
    if declared_bot_uas >= 5:
        out["ua_spoofed_bots"] = (f"{declared_bot_uas} different named-bot User-Agents from one IP; "
                                  "a real crawler has one identity, so these are spoofed")
    if probes:
        out["probe_paths"] = f"{sum(probes.values())} requests for {len(probes)} scanner path families: " + ", ".join(f"{k}={v}" for k, v in probes.most_common(4))
    if payloads:
        out["payloads"] = f"{sum(payloads.values())} requests with exploit-shaped strings: " + ", ".join(f"{k}={v}" for k, v in payloads.most_common(4))
    if waf.get("deny", 0):
        out["waf_denied"] = f"{waf['deny']} requests denied by the WAF"
    if waf.get("throttle", 0):
        out["waf_throttled"] = f"{waf['throttle']} requests rate-limited by the WAF"
    if waf.get("count", 0):
        out["waf_counted"] = f"{waf['count']} requests matched a WAF rule running in count (monitor) mode"
    if raw_ip_host:
        out["raw_ip_host"] = f"{raw_ip_host} requests addressed the server by IP instead of a hostname"
    if p["paths"]["auth_endpoint_requests"] >= 20:
        out["auth_volume"] = f"{p['paths']['auth_endpoint_requests']} requests to authentication endpoints"
    if p["paths"]["enumeration_templates"]:
        t = p["paths"]["enumeration_templates"][0]
        out["enumeration"] = f"{t['distinct_values']} distinct ids under {t['template']}"
    if p["volume"]["peak_requests_per_minute"] >= 120:
        out["burst"] = f"peak {p['volume']['peak_requests_per_minute']} requests in one minute"
    return out


def render(profile: dict, max_tokens: int, samples: dict | None = None) -> tuple[dict, int]:
    """Return (trimmed profile, estimated tokens). Shrinks sample lists until
    the JSON fits `max_tokens`. The estimate is 1.5 chars per token: measured
    with limits.py, profile JSON (slashes, UUIDs, hex ids, punctuation)
    tokenizes at 1.5-2.9 chars/token, so this errs on trimming early. The
    real count comes back in Jev's usage field and is reported per row."""
    sizes = dict(samples or DEFAULT_SAMPLES)
    while True:
        trimmed = _apply_sizes(profile, sizes)
        est = estimate_tokens(trimmed)
        if est <= max_tokens or all(v <= 2 for v in sizes.values()):
            return trimmed, est
        sizes = {k: max(2, v // 2) for k, v in sizes.items()}


def estimate_tokens(obj) -> int:
    return len(json.dumps(obj, separators=(",", ":"))) * 2 // 3 + 1


def _apply_sizes(p: dict, s: dict) -> dict:
    out = json.loads(json.dumps(p))
    out["paths"]["top"] = out["paths"]["top"][: s["top_paths"]]
    out["paths"]["error_sample"] = out["paths"]["error_sample"][: s["error_paths"]]
    out["paths"]["templates"] = out["paths"]["templates"][: s["templates"]]
    out["paths"]["directories"] = out["paths"]["directories"][: s["directories"]]
    out["paths"]["unmatched_sample"] = out["paths"]["unmatched_sample"][: s["unmatched"]]
    out["probes"]["examples"] = {k: v[:2] for k, v in list(out["probes"]["examples"].items())[: s["probe_paths"]]}
    out["payloads"]["examples"] = out["payloads"]["examples"][: s["payload_paths"]]
    out["queries"]["sample"] = out["queries"]["sample"][: s["queries"]]
    out["user_agents"]["top"] = out["user_agents"]["top"][: s["uas"]]
    out["hosts"]["top"] = out["hosts"]["top"][: s["hosts"]]
    return out


# --- word buckets -----------------------------------------------------------

def _volume_words(n: int, span_s: float, peak: int, gaps: list[float]) -> str:
    if n == 1:
        return "a single request"
    size = "a handful of" if n < 10 else "dozens of" if n < 100 else "hundreds of" if n < 1000 else "thousands of"
    span = ("within one minute" if span_s < 60 else f"over about {round(span_s / 60)} minutes" if span_s < 7200
            else f"over about {round(span_s / 3600)} hours")
    if peak >= 120:
        pace = "in aggressive bursts (well over 100 per minute at peak)"
    elif peak >= 30:
        pace = "at a fast automated pace at peak"
    elif gaps and statistics.median(gaps) > 240 and len(set(round(g / 30) for g in gaps)) <= 3:
        pace = "at a regular fixed interval, like a scheduler"
    elif gaps and statistics.median(gaps) < 1:
        pace = "back to back, faster than a person clicks"
    else:
        pace = "at a pace a person or a polite client could produce"
    return f"{size} requests {span}, {pace}"


def _response_words(n: int, ns: int, p404: int, err4: int, err5: int, ok: int) -> str:
    if ns == 0:
        return ("no response statuses in this source (a WAF or edge log that records the verdict but not the "
                "backend's answer), so success and not-found cannot be told apart here")
    if ns < n:
        return _response_words(ns, ns, p404, err4, err5, ok) + f" (statuses known for {ns} of {n} requests)"
    if p404 / n >= 0.6:
        return f"mostly not-found: {p404} of {n} requests returned 404"
    if err4 / n >= 0.5:
        return f"mostly rejected: {err4} of {n} requests returned a 4xx"
    if err5 / n >= 0.2:
        return f"causing server errors: {err5} of {n} requests returned a 5xx"
    if ok / n >= 0.8:
        return f"mostly successful: {ok} of {n} requests returned 2xx"
    return "a mix of successful and failed requests"


def _short_label(label: str) -> str:
    """awswaf:managed:aws:core-rule-set:SQLi_QueryArguments -> core-rule-set:SQLi_QueryArguments"""
    parts = label.split(":")
    return ":".join(parts[-2:]) if len(parts) > 2 else label


def _label_words(attack: Counter, bot: Counter, reputation: Counter, n: int) -> str:
    if not (attack or bot or reputation):
        return "no WAF labels recorded"
    parts = []
    if attack:
        parts.append(f"attack signatures on {sum(attack.values())} of {n} requests ({', '.join(_short_label(k) for k, _ in attack.most_common(3))})")
    if bot:
        parts.append(f"bot-control labels ({', '.join(_short_label(k) for k, _ in bot.most_common(3))})")
    if reputation:
        parts.append(f"IP reputation or anonymizer labels ({', '.join(_short_label(k) for k, _ in reputation.most_common(2))})")
    return "; ".join(parts)


def _waf_words(waf: Counter) -> str:
    d, t = waf.get("deny", 0), waf.get("throttle", 0)
    if d and t:
        return f"WAF denied {d} and rate-limited {t} requests"
    if d:
        return f"WAF denied {d} requests"
    if t:
        return f"WAF rate-limited {t} requests"
    if waf.get("allow", 0) == sum(waf.values()):
        return "every request passed the WAF"
    return "no WAF verdicts recorded (allowed, or the source does not log them)"


def _probe_words(hits: Counter, n: int) -> str:
    if not hits:
        return "no requests for well-known scanner targets"
    total = sum(hits.values())
    share = "almost all" if total / n >= 0.8 else "most" if total / n >= 0.5 else "some"
    return f"{share} requests ({total} of {n}) ask for software or files scanners look for: " + ", ".join(hits)


def _payload_words(hits: Counter) -> str:
    if not hits:
        return "no exploit-shaped strings in paths or queries"
    return f"{sum(hits.values())} requests carry exploit-shaped strings of type: " + ", ".join(hits)


def _coverage_words(n: int, distinct: int, top_n: int, top_cov: float, described: int,
                    n_templates: int, compresses: bool) -> str:
    """Tell Jev what the samples do and do not show, since it cannot count."""
    if distinct <= top_n:
        return f"every one of the {distinct} distinct paths is listed in `top`"
    parts = [f"{distinct} distinct paths; the {top_n} in `top` cover about {round(100 * top_cov)}% of requests"]
    parts.append(f"the probe, payload, static and health rules in `probes`, `payloads` and the counts above describe "
                 f"about {round(100 * described / n)}% of requests; `unmatched_sample` holds the most-requested paths none of them describe")
    if compresses:
        parts.append(f"the paths roll up into {n_templates} route templates in `templates`, the shape of an application being used")
    else:
        parts.append("the paths do not roll up into templates: almost every request is a different path, the shape of a wordlist")
    return "; ".join(parts)


def _top(counter: Counter, k: int) -> list[dict]:
    return [{"value": v or "(empty)", "requests": c} for v, c in counter.most_common(k)]


def _status_for(events: list[dict], path: str) -> str:
    c = Counter(e["status"] for e in events if e["path"] == path and e.get("status") is not None)
    return "/".join(str(s) for s, _ in c.most_common(2)) or "?"


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."
