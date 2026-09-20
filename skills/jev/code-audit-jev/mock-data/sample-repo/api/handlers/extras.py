"""More handlers for the Acme portal (fictional)."""
import hmac
import re
import zipfile
from lxml import etree
from flask import request, redirect, jsonify, make_response, send_file
from api.services.auth import require_login, current_org, SESSION_SECRET
from api.db import documents, users

ALLOWED_HOSTS = {"portal.acme.example"}


@require_login
def after_login():
    """VULN open_redirect: the next parameter is followed as given."""
    return redirect(request.args.get("next", "/"))


@require_login
def after_login_safe():
    """CLEAN: relative path only."""
    nxt = request.args.get("next", "/")
    if not nxt.startswith("/") or nxt.startswith("//") or "\\" in nxt or "@" in nxt:
        nxt = "/"
    return redirect(nxt)


def delete_via_link(doc_id: str):
    """VULN csrf: a state change on a GET route, cookie-authenticated, no token or origin check."""
    documents.delete_one({"_id": doc_id, "org_id": current_org().id})
    return redirect("/documents")


@require_login
def import_manifest():
    """VULN xml_xxe: lxml parser with entities resolved on an uploaded document."""
    parser = etree.XMLParser(resolve_entities=True)
    tree = etree.fromstring(request.get_data(), parser)
    return jsonify({"items": len(tree)})


@require_login
def import_manifest_safe():
    """CLEAN: entities and network off."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True, dtd_validation=False)
    tree = etree.fromstring(request.get_data(), parser)
    return jsonify({"items": len(tree)})


@require_login
def search_users():
    """VULN nosql_ldap_injection: the request body is the filter."""
    return jsonify(list(users.find(request.get_json() or {})))


@require_login
def search_users_safe():
    """CLEAN: fixed field and operator, input as the value."""
    name = str(request.args.get("name", ""))
    return jsonify(list(users.find({"org_id": current_org().id, "name": name})))


@require_login
def update_profile():
    """VULN mass_assignment: the body is merged wholesale into the user record."""
    user = users.find_one({"_id": request.cookies.get("uid")})
    user.update(request.get_json() or {})
    users.replace_one({"_id": user["_id"]}, user)
    return jsonify({"ok": True})


@require_login
def update_profile_safe():
    """CLEAN: an explicit allowlist of fields."""
    body = request.get_json() or {}
    patch = {k: body[k] for k in ("display_name", "timezone") if k in body}
    users.update_one({"_id": request.cookies.get("uid")}, {"$set": patch})
    return jsonify({"ok": True})


@require_login
def grep_documents():
    """VULN resource_exhaustion: a regex from input, no size or time cap, and an archive expanded blind."""
    pattern = re.compile(request.args.get("pattern", ""))
    archive = zipfile.ZipFile(request.files["bundle"])
    archive.extractall("/tmp/bundle")
    hits = [n for n in archive.namelist() if pattern.search(n)]
    return jsonify({"hits": hits})


def set_session(user_id: str):
    """VULN session_and_token_handling: cookie without Secure/HttpOnly/SameSite, token compared with ==."""
    resp = make_response(jsonify({"ok": True}))
    resp.set_cookie("session", user_id)
    presented = request.headers.get("X-Api-Token", "")
    if presented == SESSION_SECRET:
        resp.headers["X-Admin"] = "1"
    return resp


def set_session_safe(user_id: str):
    """CLEAN: hardened cookie and constant-time compare."""
    resp = make_response(jsonify({"ok": True}))
    resp.set_cookie("session", user_id, secure=True, httponly=True, samesite="Lax", max_age=3600)
    presented = request.headers.get("X-Api-Token", "")
    if hmac.compare_digest(presented, SESSION_SECRET):
        resp.headers["X-Admin"] = "1"
    return resp


@require_login
def get_invoice(invoice_id: str):
    """VULN idor: any invoice by id, no ownership check."""
    return jsonify(documents.find_one({"_id": invoice_id, "kind": "invoice"}))


@require_login
def get_invoice_safe(invoice_id: str):
    """CLEAN: scoped to the caller's org."""
    return jsonify(documents.find_one({"_id": invoice_id, "kind": "invoice", "org_id": current_org().id}))


@require_login
def upload_logo():
    """VULN upload_validation: extension check only, user filename kept, no size cap."""
    f = request.files["logo"]
    if not f.filename.lower().endswith((".png", ".jpg", ".svg")):
        return jsonify({"error": "type"}), 400
    f.save(f"/srv/acme/public/logos/{f.filename}")
    return jsonify({"ok": True})
