"""Login protection: one shared account, a signed session cookie, and a guard on every /api route.

Settings (.env / Azure app settings):
  APP_USERNAME, SECRET_KEY            required
  APP_PASSWORD_HASH                   preferred: python -c "from werkzeug.security import generate_password_hash as g; print(g('your-password'))"
  APP_PASSWORD                        plain-text alternative (used only when no hash is set)
  COOKIE_SECURE=true                  send the cookie over HTTPS only (set this when deployed)
  SESSION_HOURS=8                     login lifetime
  AUTH_DISABLED=true                  local development only: turns the login off
The React shell and static files stay public (they hold no data); everything under /api needs a login except the routes below.
"""
import hmac
import os
import time
from datetime import timedelta

from flask import jsonify, request, session
from werkzeug.security import check_password_hash

PUBLIC = {"/api/login", "/api/logout", "/api/session"}
MAX_FAILS, WINDOW = 5, 300                 # failed logins allowed per client in WINDOW seconds
_fails = {}


def disabled():
    return os.getenv("AUTH_DISABLED", "false").lower() == "true"


def check_config():
    """Fail fast: never start with the login half-configured."""
    if disabled():
        return
    missing = [k for k in ("APP_USERNAME", "SECRET_KEY") if not os.getenv(k)]
    if not (os.getenv("APP_PASSWORD_HASH") or os.getenv("APP_PASSWORD")):
        missing.append("APP_PASSWORD_HASH (or APP_PASSWORD)")
    if missing:
        raise SystemExit(f"Missing login settings in .env: {', '.join(missing)} (or set AUTH_DISABLED=true for local development)")


def _credentials_ok(username, password):
    user_ok = hmac.compare_digest(username.encode(), os.getenv("APP_USERNAME", "").encode())
    stored_hash = os.getenv("APP_PASSWORD_HASH")
    if stored_hash:
        pass_ok = check_password_hash(stored_hash, password)
    else:
        pass_ok = hmac.compare_digest(password.encode(), os.getenv("APP_PASSWORD", "").encode())
    return user_ok and pass_ok                # both are always evaluated, so timing does not reveal which was wrong


def _recent_fails(client):
    now = time.time()
    _fails[client] = [t for t in _fails.get(client, []) if now - t < WINDOW]
    return _fails[client]


def init_auth(app):
    app.secret_key = os.getenv("SECRET_KEY") or os.urandom(32)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=float(os.getenv("SESSION_HOURS", "8"))),
    )

    @app.before_request
    def guard():
        if disabled() or not request.path.startswith("/api/") or request.path in PUBLIC or session.get("user"):
            return None
        return jsonify(error="Login required"), 401

    @app.get("/api/session")
    def api_session():
        if disabled():
            return jsonify(authenticated=True, user=None, auth_enabled=False)
        user = session.get("user")
        return jsonify(authenticated=bool(user), user=user, auth_enabled=True)

    @app.post("/api/login")
    def api_login():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("username"), str) or not isinstance(body.get("password"), str):
            return jsonify(error="Enter a username and password"), 400
        client = request.remote_addr or "?"
        fails = _recent_fails(client)
        if len(fails) >= MAX_FAILS:
            return jsonify(error="Too many failed attempts. Try again in a few minutes."), 429
        if disabled() or not _credentials_ok(body["username"], body["password"]):
            fails.append(time.time())
            return jsonify(error="Wrong username or password"), 401
        _fails.pop(client, None)
        session.clear()                       # fresh session on login
        session.permanent = True
        session["user"] = os.getenv("APP_USERNAME")
        return jsonify(authenticated=True, user=session["user"], auth_enabled=True)

    @app.post("/api/logout")
    def api_logout():
        session.clear()
        return jsonify(authenticated=False)
