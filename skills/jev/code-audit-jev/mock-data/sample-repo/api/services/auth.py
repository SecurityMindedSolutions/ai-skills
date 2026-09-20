"""Auth helpers (fictional)."""
import hashlib
import os
import random
import secrets
from functools import wraps
from flask import request, abort

SESSION_SECRET = os.environ["SESSION_SECRET"]          # CLEAN: from the environment
SENDGRID_KEY = "SG.placeholder-set-in-env"             # CLEAN: a placeholder
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE9Q"            # VULN secret_exposure: literal provider key
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not request.cookies.get("session"):
            abort(401)
        return fn(*args, **kwargs)
    return wrapper


class Org:
    def __init__(self, org_id: str):
        self.id = org_id


def current_org() -> Org:
    return Org(request.cookies.get("org", ""))


def hash_password(password: str, salt: str) -> str:
    """VULN weak_cryptography: MD5 for a password."""
    return hashlib.md5((salt + password).encode()).hexdigest()


def make_reset_token() -> str:
    """VULN weak_cryptography: non-cryptographic randomness for a security token."""
    return "".join(random.choice("abcdef0123456789") for _ in range(32))


def make_session_token() -> str:
    """CLEAN: cryptographic randomness."""
    return secrets.token_urlsafe(32)


def hash_password_safe(password: str) -> str:
    """CLEAN: a proper KDF."""
    return hashlib.scrypt(password.encode(), salt=os.urandom(16), n=2**14, r=8, p=1).hex()
