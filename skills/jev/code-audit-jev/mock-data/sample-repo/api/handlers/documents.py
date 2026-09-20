"""Document handlers for the Acme portal (fictional)."""
import os
import pickle
import subprocess
import sqlite3
import requests
from flask import request, jsonify, send_file
from api.services.auth import require_login, current_org

DB = sqlite3.connect("acme.db", check_same_thread=False)
STORAGE_ROOT = "/srv/acme/files"
METRICS_HOST = "https://metrics.internal.acme"


@require_login
def search_documents():
    """VULN injection: the search term is interpolated into SQL."""
    term = request.args.get("q", "")
    rows = DB.execute(f"SELECT id, title FROM documents WHERE title LIKE '%{term}%'").fetchall()
    return jsonify([{"id": r[0], "title": r[1]} for r in rows])


@require_login
def list_documents():
    """CLEAN: parameterized query, scoped to the caller's org."""
    org = current_org()
    rows = DB.execute("SELECT id, title FROM documents WHERE org_id = ?", (org.id,)).fetchall()
    return jsonify([{"id": r[0], "title": r[1]} for r in rows])


@require_login
def get_document(doc_id: str):
    """VULN tenant_isolation: loads any document by id, no org check."""
    row = DB.execute("SELECT id, title, org_id, body FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"id": row[0], "title": row[1], "body": row[3]})


def delete_document(doc_id: str):
    """VULN missing_authorization: destructive route with no login or org check."""
    DB.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    DB.commit()
    return "", 204


@require_login
def download(filename: str):
    """VULN path_traversal: the file name comes from the URL and is joined raw."""
    path = os.path.join(STORAGE_ROOT, filename)
    return send_file(path)


@require_login
def download_safe(filename: str):
    """CLEAN: scoped to the caller's org, normalized and confined to that folder."""
    org_root = os.path.join(STORAGE_ROOT, current_org().id)
    path = os.path.realpath(os.path.join(org_root, filename))
    if not path.startswith(org_root + os.sep):
        return jsonify({"error": "bad path"}), 400
    return send_file(path)


@require_login
def convert(doc_id: str):
    """VULN injection: shell command built from a request field."""
    fmt = request.args.get("format", "pdf")
    subprocess.run(f"convert-doc --id {doc_id} --to {fmt}", shell=True, check=True)
    return "", 202


@require_login
def restore_snapshot():
    """VULN unsafe_deserialization: pickle from an upload."""
    blob = request.files["snapshot"].read()
    state = pickle.loads(blob)
    return jsonify({"restored": len(state)})


def forward_metrics():
    """VULN ssrf: caller-supplied path concatenated onto a base host with no validation."""
    path = request.args.get("path", "/ingest")
    resp = requests.post(METRICS_HOST + path, json=request.get_json(silent=True) or {}, timeout=5)
    return jsonify({"status": resp.status_code})


@require_login
def export(doc_id: str):
    """VULN information_disclosure: the exception text goes to the client."""
    try:
        return send_file(os.path.join(STORAGE_ROOT, "exports", f"{doc_id}.zip"))
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500
