"""Example builder: one item per Python module in a directory, summarized by AST.

    python3 build_spec_from_python_modules.py <dir> <questions.json> <spec.json> [--expect labels.json]

This is the pattern for any "judge every X in a tree" run: code walks the
tree and produces a compact, named-field state per item (docstring, public
symbols with their one-line docs, imports), so each request stays well under
the ~6k-token soft cap even for a 3,500-line module. Whole-file contents are
almost never the right state.

`questions.json` is the `questions` object of a spec (see references/spec-format.md).
`labels.json`, optional, is {module_stem: {qid: expected_label}} and becomes each
item's `expect`, so report.py can print agreement.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

STDLIB = {"typing", "datetime", "collections", "dataclasses", "__future__", "enum", "functools",
          "json", "logging", "os", "re", "time", "uuid", "hashlib", "hmac", "base64", "secrets",
          "urllib", "html", "io", "math", "string", "itertools", "threading", "http", "email",
          "pathlib", "contextlib", "textwrap", "unicodedata", "ipaddress", "socket", "random",
          "struct", "zlib", "copy", "operator", "abc", "concurrent", "sys", "argparse", "csv"}


def summarize(path: pathlib.Path, root: pathlib.Path) -> dict:
    tree = ast.parse(path.read_text())
    doc = (ast.get_docstring(tree) or "").strip()
    symbols, imports = [], set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            d = (ast.get_docstring(node) or "").strip().splitlines()
            symbols.append({"name": node.name, "doc": d[0] if d else ""})
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Import):
            imports.update(a.name for a in node.names)
    ext = sorted(i for i in imports if i.split(".")[0] not in STDLIB)
    return {"module": str(path.relative_to(root)), "docstring": doc[:2500],
            "public_symbols": symbols[:40], "imports": ext}


def main() -> None:
    root, qfile, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    labels = {}
    if "--expect" in sys.argv:
        labels = json.loads(pathlib.Path(sys.argv[sys.argv.index("--expect") + 1]).read_text())
    items = []
    for p in sorted(root.rglob("*.py")):
        if p.name == "__init__.py":
            continue
        item = {"id": p.stem, "state": summarize(p, root)}
        if p.stem in labels:
            item["expect"] = labels[p.stem]
        items.append(item)
    spec = {"model": "jev-latest", "concurrency": 6,
            "questions": json.loads(qfile.read_text()), "items": items}
    out.write_text(json.dumps(spec, indent=1))
    print(f"{len(items)} items -> {out}")


if __name__ == "__main__":
    main()
