"""Split a source file into units small enough for one Jev question set.

A unit is one function, method, class body, Terraform block, CI job or config
file, with its line span. Jev reads one unit at a time, so a unit must carry
what a reviewer would need to judge it without opening other files: the
file's imports and the guard names present anywhere in the file travel with
every unit as `file` context (see run.py).

Python is split with `ast` (exact). TypeScript, JavaScript, Go, Java, Rust
and Terraform are split by tracking brace depth at column 0, which is right
for well-formatted code and degrades to line chunks otherwise. YAML, JSON,
Dockerfiles, shell and everything else are one unit per file, chunked only
when they exceed the token budget.
"""

from __future__ import annotations

import ast
import re

CHARS_PER_TOKEN = 3.2          # code tokenizes denser than prose; measured on Jev usage, see methodology
MAX_UNIT_CHARS = 14_000        # ~4.4k tokens; larger units are split into chunks
CHUNK_LINES = 90
MIN_UNIT_LINES = 3             # one-line getters and constants are folded into the module unit

BRACE_DECL = re.compile(
    r"^(export\s+)?(default\s+)?(async\s+)?(function\b|class\b|const\b|let\b|var\b|interface\b|type\b|enum\b|"
    r"func\b|public\b|private\b|protected\b|static\b|resource\b|module\b|data\b|variable\b|output\b|locals\b|"
    r"provider\b|terraform\b|impl\b|fn\b|pub\b|struct\b|@\w+)")


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


def units_for(path: str, language: str, text: str) -> list[dict]:
    if language == "python":
        units = _python_units(text)
    elif language in ("typescript", "javascript", "go", "java", "kotlin", "rust", "csharp", "terraform", "php"):
        units = _brace_units(text)
    else:
        units = [_unit("file", text, 1)]
    out: list[dict] = []
    for u in units:
        out.extend(_chunk(u))
    for u in out:
        u["path"] = path
        u["language"] = language
        u["tokens_est"] = estimate_tokens(u["code"])
    return out


def _unit(name: str, code: str, start: int, kind: str = "block") -> dict:
    return {"name": name, "kind": kind, "code": code, "start": start,
            "end": start + code.count("\n")}


# --- Python -----------------------------------------------------------------

def _python_units(text: str) -> list[dict]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _line_chunks(text)
    lines = text.splitlines()
    units: list[dict] = []
    covered: set[int] = set()

    def add(node, qual: str, kind: str) -> None:
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        end = node.end_lineno or node.lineno
        code = "\n".join(lines[start - 1:end])
        units.append(_unit(qual, code, start, kind))
        covered.update(range(start, end + 1))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node, node.name, "function")
        elif isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            body_end = node.end_lineno or node.lineno
            if not methods or body_end - node.lineno < 60:
                add(node, node.name, "class")
                continue
            # class header + non-method statements as one unit, each method its own
            first_method = min(min([m.lineno] + [d.lineno for d in m.decorator_list]) for m in methods)
            header = "\n".join(lines[node.lineno - 1:first_method - 1])
            units.append(_unit(node.name, header, node.lineno, "class"))
            covered.update(range(node.lineno, first_method))
            for m in methods:
                add(m, f"{node.name}.{m.name}", "method")
            # statements between/after methods
            for stmt in node.body:
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    s, e = stmt.lineno, stmt.end_lineno or stmt.lineno
                    if s not in covered:
                        units.append(_unit(f"{node.name}.<body>", "\n".join(lines[s - 1:e]), s, "class"))
                        covered.update(range(s, e + 1))
    # everything not covered (imports, constants, top-level statements) is the module unit
    rest = [(i + 1, l) for i, l in enumerate(lines) if (i + 1) not in covered and l.strip()]
    if rest:
        # keep it contiguous-ish: join with the original line numbers as ranges
        code = "\n".join(l for _, l in rest)
        u = _unit("<module>", code, rest[0][0], "module")
        u["end"] = rest[-1][0]
        units.append(u)
    units.sort(key=lambda u: u["start"])
    return units


# --- Brace languages ----------------------------------------------------------

def _brace_units(text: str) -> list[dict]:
    lines = text.splitlines()
    units: list[dict] = []
    depth = 0
    cur_start: int | None = None
    cur_name = ""
    buf: list[str] = []
    top: list[str] = []
    top_start = 1
    in_block_comment = False

    def flush_top() -> None:
        nonlocal top
        if top and any(l.strip() for l in top):
            units.append(_unit("<module>", "\n".join(top), top_start, "module"))
        top = []

    for i, raw in enumerate(lines, start=1):
        line = raw
        # crude comment/string stripping for depth counting only
        stripped, in_block_comment = _strip_for_depth(line, in_block_comment)
        opens, closes = stripped.count("{"), stripped.count("}")
        if cur_start is None:
            if depth == 0 and opens > closes and line.strip() and not line.lstrip().startswith(("//", "#", "*", "/*")):
                # any top-level statement that opens a brace block is a unit:
                # declarations, route registrations, describe() blocks, tf resources
                flush_top()
                cur_start, cur_name, buf = i, _decl_name(line), [raw]
                depth = opens - closes
                continue
            if not top:
                top_start = i
            top.append(raw)
            depth = max(0, depth + opens - closes)
        else:
            buf.append(raw)
            depth += opens - closes
            if depth <= 0 and (opens or closes):
                units.append(_unit(cur_name, "\n".join(buf), cur_start, "block"))
                cur_start, buf, depth = None, [], 0
    if cur_start is not None:
        units.append(_unit(cur_name, "\n".join(buf), cur_start, "block"))
    flush_top()
    units = [u for u in units if u["code"].strip()]
    return _merge_fragments(units) or _line_chunks(text)


_INERT_LINE = re.compile(r"^\s*(//|#|/\*|\*|\*/|import\b|from\s+\S+\s+import\b|export\s+(type|interface)\b|$)")


def _is_inert(code: str) -> bool:
    """Comments, blanks and imports only: safe to fold into the next block. A
    fragment with a real statement (a constant, a call) stays its own unit so
    a secret literal is reported where it is, not inside the next function."""
    return all(_INERT_LINE.match(l) for l in code.splitlines())


def _merge_fragments(units: list[dict], max_lines: int = 8) -> list[dict]:
    """A comment or blank run between two blocks is not a unit of its own; it
    is the leading comment of the next block (or the trailer of the last)."""
    out: list[dict] = []
    pending: dict | None = None
    for u in units:
        if u["kind"] == "module" and (u["end"] - u["start"] + 1) <= max_lines and _is_inert(u["code"]):
            pending = u if pending is None else _unit("<module>", pending["code"] + "\n" + u["code"], pending["start"], "module")
            continue
        if pending is not None:
            u = dict(u, code=pending["code"] + "\n" + u["code"], start=pending["start"])
            pending = None
        out.append(u)
    if pending is not None:
        if out:
            last = out[-1]
            out[-1] = dict(last, code=last["code"] + "\n" + pending["code"], end=pending["end"])
        else:
            out.append(pending)
    return out


def _continues(lines: list[str], i: int) -> bool:
    nxt = lines[i] if i < len(lines) else ""
    return nxt.strip().startswith("{") or "{" in nxt


def _strip_for_depth(line: str, in_block: bool) -> tuple[str, bool]:
    out = []
    i = 0
    n = len(line)
    quote = None
    # a quote character with an odd count on the line is an apostrophe in
    # prose or JSX text, not a string delimiter; ignore it for depth counting
    delimiters = {c for c in ("'", '"', "`") if line.count(c) % 2 == 0}
    while i < n:
        ch = line[i]
        if in_block:
            if line.startswith("*/", i):
                in_block = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if line.startswith("//", i) or ch == "#" and not line[:i].strip():
            break
        if line.startswith("/*", i):
            in_block = True
            i += 2
            continue
        if ch in delimiters:
            quote = ch
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out), in_block


def _decl_name(line: str) -> str:
    m = re.search(r"(?:function|class|interface|type|enum|const|let|var|func|fn|struct|impl)\s+\*?\(?\s*([\w$.]+)", line)
    if m:
        return m.group(1)
    m = re.search(r'^(resource|module|data|variable|output|provider)\s+"([^"]+)"(?:\s+"([^"]+)")?', line.strip())
    if m:
        return ".".join(x for x in m.groups() if x)
    m = re.search(r"^\s*(?:public|private|protected|static|async|export|default)?\s*([\w$]+)\s*\(", line)
    return m.group(1) if m else line.strip()[:40]


# --- Fallback and chunking -------------------------------------------------

def _line_chunks(text: str) -> list[dict]:
    lines = text.splitlines()
    return [_unit(f"lines {i + 1}-{min(i + CHUNK_LINES, len(lines))}", "\n".join(lines[i:i + CHUNK_LINES]), i + 1, "chunk")
            for i in range(0, len(lines), CHUNK_LINES)]


def _chunk(u: dict) -> list[dict]:
    if len(u["code"]) <= MAX_UNIT_CHARS:
        return [u]
    lines = u["code"].splitlines()
    per = max(20, int(len(lines) * MAX_UNIT_CHARS / len(u["code"])))
    out = []
    for i in range(0, len(lines), per):
        part = "\n".join(lines[i:i + per])
        c = _unit(f"{u['name']} [part {i // per + 1}]", part, u["start"] + i, u["kind"])
        out.append(c)
    return out


def file_context(text: str, language: str) -> dict:
    """Imports and guard/decorator names anywhere in the file: what a unit
    inherits from its surroundings without Jev having to read the whole file."""
    lines = text.splitlines()
    imports = [l.strip() for l in lines if re.match(r"^\s*(import\b|from\s+\S+\s+import\b|require\(|use\b|#include|using\b)", l)]
    imports = imports[:40]
    guards = sorted(set(m.group(0) for m in re.finditer(
        r"@\w*(auth|login|permission|role|guard|secure|protect|require|admin|csrf)\w*|"
        r"\b(require_auth|requires_auth|login_required|require_role|require_capability|check_permission|authorize|authenticate|"
        r"verify_id_token|verify_token|get_current_user|current_user|ensure_member|require_member|require_owner|"
        r"UseGuards|PreAuthorize|isAuthenticated|requireAuth|withAuth|[A-Za-z]+Level\.\w+|auth_level\s*=\s*\w+|"
        r"[A-Z_]+_REQUIRED|PUBLIC|NONE|ANONYMOUS|capabilit\w+|permission_classes)\b", text, re.I)))
    return {"imports": imports, "guard_markers": guards[:30], "lines": len(lines)}


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("file")
    p.add_argument("--language")
    a = p.parse_args()
    path = Path(a.file)
    lang = a.language or {"py": "python", "ts": "typescript", "tsx": "typescript", "js": "javascript", "tf": "terraform"}.get(path.suffix[1:], "text")
    txt = path.read_text(errors="replace")
    for u in units_for(str(path), lang, txt):
        print(f"{u['start']:5d}-{u['end']:<5d} {u['kind']:8} {u['tokens_est']:5d}tok  {u['name']}")
    print(json.dumps(file_context(txt, lang), indent=1))
