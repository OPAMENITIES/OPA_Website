"""
On Point Amenities — Lead Capture Serverless Function (Vercel)
Flask WSGI app — exposes `app` variable as required by Vercel Python runtime.
Sends each lead to OVM's CRM (POST /api/crm/leads), which creates the
contact, company, site, deal, note and follow-up tasks.
"""
import json
import os
import re
import urllib.request
import urllib.error
from flask import Flask, request, jsonify, redirect

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024  # 32KB body cap

ALLOWED_ORIGIN = "https://opamenities.com"

FIELD_LIMITS = {
    "first_name": 80, "last_name": 80, "email": 120, "phone": 30,
    "property_name": 120, "property_type": 60, "num_residents": 40,
    "city": 80, "message": 2000, "company_website": 200,
    "ts": 20, "tk": 20,
}
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")

# ---- Bot defense (Turnstile-class, zero external deps) --------------------
# ts = epoch-ms the form was rendered (set by JS); tk = base36(ts % 997593).
# Bots that POST without executing JS, or faster than a human can type, are
# dropped with a FAKE success (same philosophy as the honeypot: teach nothing).
# Warm-instance state: rate limiting + duplicate suppression. Serverless
# instances are ephemeral, so this is a burst damper, not a ledger — which is
# exactly the threat model for a lead form.
import time as _time

TOKEN_MOD = 997593
MIN_DWELL_MS = 3000            # faster than any human fills 5 required fields
MAX_DWELL_MS = 48 * 3600_000   # stale page

_ip_hits = {}                  # ip -> [epoch_s, ...]
_all_hits = []                 # instance-wide
_recent_leads = {}             # (email, property) -> epoch_s
RATE_WINDOW = 600
RATE_PER_IP = 3
RATE_GLOBAL = 30
DEDUPE_WINDOW = 600


def _b36(n: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "0"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    return out


def bot_verdict(clean: dict, js_client: bool) -> str:
    """Returns '' if human-plausible, else a drop reason."""
    ts, tk = clean.get("ts", ""), clean.get("tk", "")
    if not ts and not tk and not js_client:
        return ""  # grace: no-JS form post; honeypot and rate limit still apply
    if not ts.isdigit():
        return "ts-malformed"
    if tk != _b36(int(ts) % 997593):
        return "tk-mismatch"
    if tk != _b36(int(ts) % TOKEN_MOD):
        return "token-mismatch"
    dwell = int(_time.time() * 1000) - int(ts)
    if dwell < MIN_DWELL_MS:
        return "too-fast (%dms)" % dwell
    if dwell > MAX_DWELL_MS:
        return "stale (%dms)" % dwell
    return ""


def rate_limited(ip: str) -> bool:
    now = _time.time()
    cut = now - RATE_WINDOW
    _all_hits[:] = [t for t in _all_hits if t > cut]
    hits = _ip_hits.setdefault(ip, [])
    hits[:] = [t for t in hits if t > cut]
    if len(hits) >= RATE_PER_IP or len(_all_hits) >= RATE_GLOBAL:
        return True
    hits.append(now)
    _all_hits.append(now)
    return False


def duplicate_lead(clean: dict) -> bool:
    key = (clean["email"].lower(), clean["property_name"].lower())
    now = _time.time()
    for k in [k for k, t in _recent_leads.items() if now - t > DEDUPE_WINDOW]:
        del _recent_leads[k]
    if key in _recent_leads:
        return True
    _recent_leads[key] = now
    return False


def forget_lead(clean: dict) -> None:
    """Un-mark a lead whose CRM write failed, so the visitor's retry isn't suppressed."""
    _recent_leads.pop((clean["email"].lower(), clean["property_name"].lower()), None)


def validate_payload(data):
    """Returns (clean_dict, error_string_or_None). Strings only, capped lengths."""
    if not isinstance(data, dict):
        return None, "invalid"
    clean = {}
    for k, cap in FIELD_LIMITS.items():
        v = data.get(k, "")
        if v is None:
            v = ""
        if not isinstance(v, str):
            return None, "invalid"
        v = v.strip()
        if len(v) > cap:
            v = v[:cap]
        clean[k] = v
    required = ["first_name", "last_name", "email", "property_name", "city"]
    missing = [f for f in required if not clean[f]]
    if missing:
        return None, "missing"
    if not EMAIL_RE.match(clean["email"]):
        return None, "email"
    return clean, None

OVM_LEAD_INTAKE_URL = os.environ.get("OVM_LEAD_INTAKE_URL", "").strip()
CRM_LEAD_INTAKE_KEY = os.environ.get("CRM_LEAD_INTAKE_KEY", "").strip()


def create_ovm_lead(form: dict) -> dict:
    """Send the lead to OVM's CRM (POST /api/crm/leads).

    OVM creates the contact, company, site, deal, note and follow-up tasks in
    one transaction, so a failure here leaves nothing half-written and the
    visitor can safely retry.
    """
    if not OVM_LEAD_INTAKE_URL or not CRM_LEAD_INTAKE_KEY:
        return {"success": False, "error": "OVM lead intake not configured", "step": "config"}

    payload = {
        "firstName": form.get("first_name", ""),
        "lastName": form.get("last_name", ""),
        "email": form.get("email", ""),
        "phone": form.get("phone") or None,
        "propertyName": form.get("property_name", ""),
        "propertyType": form.get("property_type") or None,
        "residentsOrEmployees": form.get("num_residents") or None,
        "city": form.get("city", ""),
        "message": form.get("message") or None,
    }
    req = urllib.request.Request(
        OVM_LEAD_INTAKE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Lead-Intake-Key": CRM_LEAD_INTAKE_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}", "step": "ovm"}
    except Exception as e:  # timeout, DNS, connection reset, bad JSON
        return {"success": False, "error": type(e).__name__, "step": "ovm"}

    if status not in (200, 201) or body.get("status") != "OK":
        return {"success": False, "error": f"HTTP {status}", "step": "ovm"}
    return {
        "success": True,
        "person_id": body.get("personId"),
        "deal_id": body.get("dealId"),
        "duplicate": bool(body.get("duplicate")),
    }


@app.route("/api/submit-lead", methods=["OPTIONS"], strict_slashes=False)
def submit_lead_options():
    response = jsonify({})
    response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response, 200


def _cors(response):
    response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
    return response


THANKS = "Thank you! We'll be in touch within 24 hours."


def _reply(form_post: bool, ok: bool, text: str, code: int):
    """JSON for the page script. A no-JS form post gets the thank-you page or a plain error page."""
    if not form_post:
        body = {"success": True, "message": text} if ok else {"success": False, "error": text}
        return _cors(jsonify(body)), code
    if ok:
        return redirect("/thank-you/", code=303)
    html = ("<!doctype html><meta charset=utf-8><title>On Point Amenities</title>"
            "<p>" + text + "</p><p><a href=\"/contact/\">Back to the form</a></p>")
    return html, code, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/submit-lead", methods=["POST"], strict_slashes=False)
def submit_lead():
    form_post = request.mimetype in ("application/x-www-form-urlencoded", "multipart/form-data")
    try:
        # Rate limit before any parsing — cheapest rejection first.
        ip = (request.headers.get("x-forwarded-for", "") or request.remote_addr or "?").split(",")[0].strip()
        if rate_limited(ip):
            print(f"[lead] rate-limited ip={ip}")
            return _reply(form_post, False, "Too many requests. Please email info@opamenities.com or call (720) 828-2170.", 429)

        if form_post:
            data = request.form.to_dict()
        else:
            try:
                data = request.get_json(force=True)
            except Exception:
                return _reply(form_post, False, "Invalid request.", 400)

        clean, err = validate_payload(data or {})
        if err == "missing":
            return _reply(form_post, False, "Please fill in the required fields.", 400)
        if err == "email":
            return _reply(form_post, False, "Please enter a valid email address.", 400)
        if err:
            return _reply(form_post, False, "Invalid request.", 400)

        # Honeypot: bots fill the hidden field. Pretend success; write nothing.
        if clean.get("company_website"):
            print("[lead] honeypot tripped — dropping submission")
            return _reply(form_post, True, THANKS, 200)

        verdict = bot_verdict(clean, js_client=not form_post)
        if verdict:
            print(f"[lead] bot verdict={verdict} — dropping submission")
            return _reply(form_post, True, THANKS, 200)
        if not clean.get("ts"):
            print("[lead] no-JS form post (grace-accepted)")

        # Idempotency: double-click / repeat within 10 min — succeed without a second CRM write.
        if duplicate_lead(clean):
            print("[lead] duplicate suppressed")
            return _reply(form_post, True, THANKS, 200)

        result = create_ovm_lead(clean)

        if result.get("success"):
            print(f"[lead] created: person={result.get('person_id','?')} deal={result.get('deal_id','?')}")
            return _reply(form_post, True, THANKS, 200)
        else:
            forget_lead(clean)
            print(f"[lead] CRM error at step={result.get('step')}: {result.get('error')}")
            return _reply(form_post, False, "We had trouble saving your request. Please email info@opamenities.com or call (720) 828-2170.", 500)

    except Exception as e:
        print(f"[lead] unhandled error: {type(e).__name__}: {e}")
        return _reply(form_post, False, "Something went wrong. Please email info@opamenities.com or call (720) 828-2170.", 500)
