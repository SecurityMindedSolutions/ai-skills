#!/usr/bin/env python3
"""
Build a vendor dossier HTML from a spec JSON, reusing the styled shell (and all
the print fixes) from assets/template.html. The spec carries the human
judgement - categorization, plain-English "what it's for", and the verbatim
proof - that the extractor can't produce on its own.

Usage: build_dossier.py <spec.json> <out.html>

Spec shape:
{
  "classif": "Built-With",
  "target_label": "Target: app.example.com / Example Inc.",
  "title": "What Example runs on",
  "subtitle": "One-line framing.",
  "prepared_by": "Example Corp",   # optional
  "prepared_for": "Internal recon",                   # optional
  "meta": [["Method","..."],["Source","..."],["Vendors","..."],["Captured","..."]],
  "groups": [
    {"cat":"cust|infra|internal", "label":"...", "desc":"...",
     "rows":[{"name":"VendorName","role":"short role","what":"...html...",
              "sure":{"cls":"ok","label":"CONFIRMED"},"proof":"...html..."}]}
  ],
  "notes": [{"tag":"PII","kind":"flag|note","html":"..."}]
}
"""
import html as _html, json, sys

def esc(s):  # spec fields may contain intentional inline HTML, so callers pass raw
    return s

def chip(sure):
    return f'<span class="chip {sure["cls"]}">{esc(sure["label"])}</span>'

def row(r):
    return (
      '<div class="tr">'
      f'<div class="c-vendor">{esc(r["name"])} <small>{esc(r.get("role",""))}</small></div>'
      f'<div class="c-what">{esc(r["what"])}</div>'
      f'<div class="c-sure">{chip(r["sure"])}</div>'
      f'<div class="c-proof">{esc(r["proof"])}</div>'
      '</div>')

def group(g):
    head = ('<div class="tr head"><div>What they use</div><div>What it\'s for</div>'
            '<div>How sure</div><div>Prove it</div></div>')
    rows = "\n".join(row(r) for r in g["rows"])
    return (
      f'<div class="group {g["cat"]}">'
      f'<div class="group-head"><span class="catdot" style="background:var(--cat-{g["cat"]})"></span>'
      f'<h3>{esc(g["label"])}</h3></div>'
      f'<p class="group-desc">{esc(g.get("desc",""))}</p>'
      f'<div class="tbl">{head}\n{rows}</div></div>')

def host_hero(host):
    labels = host.split(".")
    if len(labels) >= 2:
        apex = ".".join(labels[-2:]); pre = ".".join(labels[:-2])
        return (f'{esc(pre)}.' if pre else '') + f'<span class="apex">{esc(apex)}</span>'
    return esc(host)

def _norm_seg(s):
    """Collapse variable path segments so /jobs/${id}/ and /jobs/${x}/ merge."""
    return "{id}" if ("${" in s or s.startswith("$") or s == "%7B") else s

def _api_tree(eps):
    root = {}   # seg -> {"count": int, "kids": {...}}
    for e in eps:
        segs = [_norm_seg(s) for s in e.split("/") if s]
        node = root
        for s in segs:
            entry = node.setdefault(s, {"count": 0, "kids": {}})
            entry["count"] += 1
            node = entry["kids"]
    return root

def _seg_html(seg):
    return f'<span class="idvar">{esc(seg)}</span>' if seg == "{id}" else esc(seg)

def _common_prefix_segs(eps):
    """Longest leading path shared by every endpoint (e.g. ['api'])."""
    lists = [[_norm_seg(s) for s in e.split("/") if s] for e in eps]
    if not lists:
        return []
    common = []
    for i in range(min(len(x) for x in lists)):
        col = {x[i] for x in lists}
        if len(col) == 1:
            common.append(next(iter(col)))
        else:
            break
    return common

def _render_tree(node, prefix, depth, max_depth, base, out):
    for seg in sorted(node, key=lambda s: (s == "{id}", s)):
        entry = node[seg]
        path = prefix + "/" + seg
        has_deeper = bool(entry["kids"])
        collapsed = has_deeper and depth >= max_depth
        shown = "/".join(_seg_html(s) for s in path.split("/") if s)
        tail = "/&hellip;" if collapsed else ("/" if has_deeper else "")
        rel = depth - base            # 1 = first visible level
        cls = "lvl-top" if rel <= 1 else ("lvl-sub" if rel == 2 else "lvl-deep")
        out.append(
            f'<div class="api-node {cls}" style="padding-left:{max(0, rel - 1) * 15}px">'
            f'<code>/{shown}{tail}</code>'
            f'<span class="cnt">{entry["count"]} route{"s" if entry["count"]!=1 else ""}</span></div>')
        if has_deeper and depth < max_depth:
            _render_tree(entry["kids"], path, depth + 1, max_depth, base, out)

def _tree_html(eps, api_depth):
    """Render a set of endpoint paths as a collapsed tree; return (rows, n, groups, prefix)."""
    tree = _api_tree(eps)
    common = _common_prefix_segs(eps)
    b = len(common)
    sub = tree
    for c in common:
        sub = sub[c]["kids"]
    prefix = "/" + "/".join(common) if common else ""
    eff = max(api_depth, b + 1)
    top = {"/" + "/".join(_norm_seg(x) for x in [y for y in e.split("/") if y][:b + 1]) for e in eps}
    rows = []
    _render_tree(sub, prefix, b + 1, eff, b, rows)
    return "".join(rows), len(eps), len(top), prefix

def enumeration_sections(report, start_num=3, api_depth=3):
    """Build the Domains & assets + per-host API surface appendices from a report.json."""
    if not report:
        return ""
    host = report.get("host", "")
    base = ".".join(host.split(".")[-2:]) if host else ""
    hosts = report.get("hostnames", {})
    own = set(h for h in hosts if base and (h == base or h.endswith("." + base)))
    ext = sorted(h for h in hosts if not (base and (h == base or h.endswith("." + base))))
    # the analyzed host is a subdomain too, even if the bundle never names it absolutely
    input_host_early = report.get("host", "")
    if input_host_early and (input_host_early == base or input_host_early.endswith("." + base)):
        own.add(input_host_early)
    own = sorted(own)
    apisurf = report.get("api_surface", {}) or {}
    api_hosts = apisurf.get("hosts", {})
    backend = apisurf.get("backend")
    input_host = report.get("host", "")
    eps = report.get("api_endpoints", [])

    # hosts we actually enumerated endpoints for (the app + any subdomain whose
    # paths are literally in the JS). Only these are claimed as having an API.
    endpoint_hosts = set()
    if eps:
        endpoint_hosts.add(input_host)
    endpoint_hosts |= {h for h in api_hosts if api_hosts[h].get("paths")}
    out = ""

    # ---- Domains & assets ----
    if own or ext:
        def own_li(h):
            star = (' <span class="apistar" title="API endpoints found">*</span>'
                    if h in endpoint_hosts else '')
            return f'<li><b>{esc(h)}</b>{star}</li>'
        blocks = ""
        if own:
            items = "".join(own_li(h) for h in own)
            blocks += (f'<div class="enum-sub"><h3>{esc(base)} subdomains &mdash; '
                       f'often a map of internal services ({len(own)})</h3>'
                       f'<ul class="enum">{items}</ul></div>')
        if ext:
            items = "".join(f'<li>{esc(h)}</li>' for h in ext)
            blocks += (f'<div class="enum-sub"><h3>Other hosts referenced ({len(ext)})</h3>'
                       f'<ul class="enum">{items}</ul></div>')
        star_note = (' A <span class="apistar">*</span> marks a host we pulled API endpoints for '
                     '(see API surface below).' if any(h in endpoint_hosts for h in own) else '')
        out += (f'<section id="assets"><div class="wrap">'
                f'<div class="sec-head"><span class="sec-num">{start_num:02d}</span>'
                f'<h2>Domains &amp; assets found</h2></div>'
                '<p class="sec-sub">Hosts referenced by the app\'s own code &mdash; the target\'s own '
                'subdomains (frequently a map of its internal services and environments), plus the '
                f'external hosts it talks to.{star_note}</p>'
                f'{blocks}</div></section>')
        start_num += 1

    # ---- API surface: only hosts we found real paths for; app first ----
    sections = []   # (host, rows, n, groups, prefix, note)
    if eps:
        rows, n, ntop, prefix = _tree_html(eps, api_depth)
        note = (f' The app calls these against its backend <code>{esc(backend)}</code> '
                '(declared in the page CSP).' if backend and backend != input_host else '')
        sections.append((input_host, rows, n, ntop, prefix, note))
    for h in sorted(api_hosts):
        if h != input_host and api_hosts[h].get("paths"):
            rows, n, ntop, prefix = _tree_html(api_hosts[h]["paths"], api_depth)
            sections.append((h, rows, n, ntop, prefix, ''))

    if sections:
        body = ""
        for hh, rows, n, ntop, prefix, note in sections:
            pn = f' All routes sit under <code>{esc(prefix)}</code>.' if prefix else ''
            body += (f'<h3 class="apihost">API surface &mdash; <code>{esc(hh)}</code></h3>'
                     f'<p class="sec-sub" style="margin:2px 0 6px">{n} route{"s" if n!=1 else ""} '
                     f'across {ntop} group{"s" if ntop!=1 else ""}.{pn}{note}</p>{rows}')
        out += (f'<section id="apis"><div class="wrap">'
                f'<div class="sec-head"><span class="sec-num">{start_num:02d}</span>'
                f'<h2>API surface</h2></div>'
                '<p class="sec-sub">Endpoints found in the JavaScript, shown for the host that serves '
                'them. Other subdomains appear in Domains &amp; assets above; the app reaches those '
                'through a runtime base-URL, so their routes are not in the bundle to enumerate. '
                'Variable segments (an id in the path) collapse to <code>{id}</code>; a trailing '
                '<code>/&hellip;</code> means more routes sit below the shown depth.</p>'
                f'{body}</div></section>')
    return out

def build(spec, head_html, report=None, api_depth=3):
    prepared = ""
    if spec.get("prepared_by") or spec.get("prepared_for"):
        cells = []
        if spec.get("prepared_by"):
            cells.append(f'<div class="prep-cell"><span class="pl">Prepared by</span>'
                         f'<span class="pv">{esc(spec["prepared_by"])}</span></div>')
        if spec.get("prepared_for"):
            if cells: cells.append('<div class="prep-div" aria-hidden="true"></div>')
            cells.append(f'<div class="prep-cell"><span class="pl">Prepared for</span>'
                         f'<span class="pv">{esc(spec["prepared_for"])}</span></div>')
        prepared = f'<div class="prepared">{"".join(cells)}</div>'
    meta = "".join(f'<div class="meta-cell"><div class="k">{esc(k)}</div>'
                   f'<div class="v">{esc(v)}</div></div>' for k, v in spec.get("meta", []))

    legend = '''<section id="legend"><div class="wrap">
      <div class="sec-head"><span class="sec-num">00</span><h2>How to read the tables</h2></div>
      <p class="sec-sub">Two things to keep straight: <b>what a vendor is for</b>, and <b>how sure we are</b> it's really doing that.</p>
      <div class="legend">
        <div class="legend-block"><h3>The three uses</h3>
          <div class="legend-row"><span class="catdot" style="background:var(--cat-cust)"></span><span><b>Customer-connected.</b> The customer sets it up themselves. Part of what they sell.</span></div>
          <div class="legend-row"><span class="catdot" style="background:var(--cat-infra)"></span><span><b>Behind-the-scenes.</b> Powers a feature, but the customer never sees the vendor's name.</span></div>
          <div class="legend-row"><span class="catdot" style="background:var(--cat-internal)"></span><span><b>Internal.</b> Hosting, monitoring, analytics. Runs the company, not the feature.</span></div>
        </div>
        <div class="legend-block"><h3>How sure</h3>
          <div class="legend-row"><span class="chip ok">Confirmed</span><span>We can see it working &mdash; live code, on-screen text, or a server header.</span></div>
          <div class="legend-row"><span class="chip high">High</span><span>Not branded, but the fingerprints only fit this one vendor.</span></div>
          <div class="legend-row"><span class="chip maybe">Likely</span><span>Mentioned in the code, but we didn't pull the final smoking gun.</span></div>
        </div>
      </div></div></section>'''

    groups = "\n".join(group(g) for g in spec["groups"])
    tables = ('<section id="tables"><div class="wrap">'
      '<div class="sec-head"><span class="sec-num">01</span><h2>The vendor map</h2></div>'
      '<p class="sec-sub">One table per use. In <b>Prove it</b>, anything in '
      '<span class="q" style="font-style:italic">"quotation marks"</span> is the target\'s own '
      'text copied word-for-word from their code, and anything in <code>monospace</code> is their '
      'exact endpoint, header, or config. Only the <b>What it\'s for</b> column is our reading.</p>'
      f'{groups}</div></section>')

    notes = ""
    if spec.get("notes"):
        items = "".join(
          f'<div class="flag {("note" if n.get("kind")=="note" else "")}">'
          f'<span class="fi">{esc(n["tag"])}</span><p>{esc(n["html"])}</p></div>'
          for n in spec["notes"])
        notes = ('<section id="notes"><div class="wrap">'
          '<div class="sec-head"><span class="sec-num">02</span><h2>Things to keep in mind</h2></div>'
          f'<div class="flags">{items}</div></div></section>')

    # Only stamp an author if the caller provides one (via the spec, or an
    # optional branding.json at the skill root). With neither, the dossier is
    # unbranded - correct for a tool that runs on arbitrary sites.
    footer_by = ""
    if spec.get("prepared_by"):
        pf = f" for {esc(spec['prepared_for'])}" if spec.get("prepared_for") else ""
        footer_by = (f'<p style="margin:14px 0 0;color:var(--ink-2)">'
          f'<b style="color:var(--ink)">Prepared by {esc(spec["prepared_by"])}{pf}.</b> '
          'Confidential &mdash; analysis based solely on publicly available information.</p>')
    links = spec.get("footer_links") or []
    if links:
        parts = ' &nbsp;&middot;&nbsp; '.join(
            f'<a href="{esc(u)}" target="_blank" rel="noopener">{esc(t)}</a>' for t, u in links)
        footer_by += f'<p style="margin:8px 0 0">{parts}</p>'

    host = spec.get("host") or ""
    eyebrow = spec.get("org") or spec.get("target_label", "")
    subtitle_h = (f'<h1 class="subtitle-h">{esc(spec["title"])}</h1>'
                  if spec.get("title") else "")
    header = (f'<header class="dossier"><div class="wrap dossier-inner">'
      f'<div class="tag-row"><span class="classif">{esc(spec.get("classif","Built-With"))}</span>'
      f'<span class="eyebrow">{esc(eyebrow)}</span></div>'
      f'<div class="host-hero">{host_hero(host)}</div>'
      f'{subtitle_h}'
      f'<p class="lede">{esc(spec.get("subtitle",""))}</p>'
      f'{prepared}<div class="meta-grid">{meta}</div></div></header>')

    footer = ('<footer><div class="wrap">'
      '<p class="mono">BUILT-WITH &middot; passive analysis of publicly-served assets and response headers</p>'
      '<p style="margin:6px 0 0">Evidence quoted from the production JS bundle and HTTP responses. No authenticated '
      'endpoints were exercised; the API surface was read from client code, not hit with credentials.</p>'
      f'{footer_by}</div></footer>')

    # appendix sections are numbered after notes (02): assets=03, apis=04
    appendix = enumeration_sections(report, start_num=3, api_depth=api_depth)
    return head_html + "\n" + header + legend + tables + notes + appendix + footer

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Build a built-with dossier from a spec JSON.")
    ap.add_argument("spec"); ap.add_argument("out")
    ap.add_argument("report", nargs="?", help="run's report.json (drives the appendices)")
    ap.add_argument("--api-depth", type=int, default=3,
                    help="how many path levels deep to expand the API tree (default 3)")
    args = ap.parse_args()
    spec = json.load(open(args.spec))
    skill_root = __file__.rsplit('/scripts/', 1)[0]
    # Optional branding.json at the skill root supplies default author + links.
    # Shipped copies omit this file, so the default output is unbranded.
    import os as _os
    bpath = _os.path.join(skill_root, "branding.json")
    if _os.path.isfile(bpath):
        try:
            b = json.load(open(bpath))
            for k in ("prepared_by", "prepared_for", "footer_links"):
                if k in b and not spec.get(k):
                    spec[k] = b[k]
        except Exception:
            pass
    tmpl = open(f"{skill_root}/assets/template.html").read()
    head = tmpl[:tmpl.index('</style>') + len('</style>')]
    # swap the <title> to the new one
    import re
    if spec.get("title"):
        head = re.sub(r'<title>.*?</title>', f'<title>{esc(spec.get("doc_title", spec["title"]))}</title>', head, count=1)
    # report.json drives the Domains & assets + API surface appendices.
    report = None
    report_path = args.report or spec.get("report")
    depth = spec.get("api_depth", args.api_depth)
    if report_path and _os.path.isfile(report_path):
        try:
            report = json.load(open(report_path))
            spec.setdefault("host", report.get("host", ""))
        except Exception:
            pass
    out = build(spec, head, report, api_depth=depth)
    open(args.out, "w").write(out)
    print(f"wrote {args.out} ({len(out)} bytes)")

if __name__ == "__main__":
    main()
