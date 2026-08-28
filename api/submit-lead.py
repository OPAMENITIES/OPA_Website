"""
OnPoint Amenities — Lead Capture Serverless Function (Vercel)
Flask WSGI app — exposes `app` variable as required by Vercel Python runtime.
Creates: Person -> Company -> Property -> Deal -> Task in Attio CRM.
"""
import json
import os
import re
import datetime
import urllib.request
import urllib.error
from flask import Flask, request, jsonify

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


def bot_verdict(clean: dict) -> str:
    """Returns '' if human-plausible, else a drop reason."""
    ts, tk = clean.get("ts", ""), clean.get("tk", "")
    if not ts and not tk:
        return ""  # grace: old cached page or JS-less edge case; honeypot still applies
    if not ts.isdigit():
        return "ts-malformed"
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

ATTIO_API_KEY = os.environ.get("ATTIO_API_KEY", "").strip()
ATTIO_BASE = "https://api.attio.com/v2"
WORKSPACE_MEMBER_ID = "9877069d-f1a4-498e-a3aa-c2120d40317c"
STAGE_NEW_INBOUND = "7b741213-46db-44b4-a245-52f6ead33850"


def attio_request(method: str, path: str, payload: dict = None, params: dict = None) -> tuple:
    url = f"{ATTIO_BASE}{path}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"
    headers = {
        "Authorization": f"Bearer {ATTIO_API_KEY}",
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}"


def create_attio_lead(form: dict) -> dict:
    results = {}
    first = form.get("first_name", "").strip()
    last = form.get("last_name", "").strip()
    email = form.get("email", "").strip()
    phone_raw = form.get("phone", "").strip()
    property_name = form.get("property_name", "").strip()
    property_type = form.get("property_type", "").strip()
    num_residents = form.get("num_residents", "").strip()
    city = form.get("city", "").strip()
    message = form.get("message", "").strip()
    phone = normalize_phone(phone_raw) if phone_raw else None

    # STEP 1: Upsert Person
    person_values = {
        "name": [{"first_name": first, "last_name": last, "full_name": f"{first} {last}"}],
        "email_addresses": [{"email_address": email}],
        "job_title": "Property Manager",
    }
    if phone:
        person_values["phone_numbers"] = [{"original_phone_number": phone}]

    status, resp = attio_request(
        "PUT", "/objects/people/records",
        {"data": {"values": person_values}},
        params={"matching_attribute": "email_addresses"}
    )
    if status not in (200, 201):
        return {"success": False, "error": f"Person creation failed: {resp.get('message', str(resp))}", "step": "person"}
    person_id = resp["data"]["id"]["record_id"]
    results["person_id"] = person_id

    # STEP 2: Create or find Company
    status, resp = attio_request(
        "POST", "/objects/companies/records/query",
        {"filter": {"name": {"$eq": property_name}}, "limit": 1}
    )
    if status == 200 and resp.get("data"):
        company_id = resp["data"][0]["id"]["record_id"]
    else:
        status, resp = attio_request(
            "POST", "/objects/companies/records",
            {"data": {"values": {"name": [{"value": property_name}]}}}
        )
        if status not in (200, 201):
            return {"success": False, "error": f"Company creation failed: {resp.get('message', str(resp))}", "step": "company"}
        company_id = resp["data"]["id"]["record_id"]
    results["company_id"] = company_id

    # STEP 3: Upsert Property
    status, resp = attio_request(
        "PUT", "/objects/properties/records",
        {
            "data": {
                "values": {
                    "property_name": [{"value": property_name}],
                    "associated_company": [{"target_object": "companies", "target_record_id": company_id}],
                    "primary_contact": [{"target_object": "people", "target_record_id": person_id}],
                }
            }
        },
        params={"matching_attribute": "property_name"}
    )
    property_id = None
    if status in (200, 201):
        property_id = resp["data"]["id"]["record_id"]
        results["property_id"] = property_id

    # STEP 4: Create Deal
    deal_name = f"Website Lead — {property_name} ({city})"
    note_text = (
        f"Source: Website Form\nCity: {city}\n"
        f"Property Type: {property_type}\n"
        f"Residents/Employees: {num_residents}\nMessage: {message}"
    )
    deal_values = {
        "name": [{"value": deal_name}],
        "stage": [{"status": STAGE_NEW_INBOUND}],
        "owner": [{"referenced_actor_type": "workspace-member", "referenced_actor_id": WORKSPACE_MEMBER_ID}],
        "associated_people": [{"target_object": "people", "target_record_id": person_id}],
        "associated_company": [{"target_object": "companies", "target_record_id": company_id}],
        "notes_did_you_meet_the_decision_maker": [{"value": note_text}],
    }
    if property_id:
        deal_values["associated_property"] = [{"target_object": "properties", "target_record_id": property_id}]

    status, resp = attio_request("POST", "/objects/deals/records", {"data": {"values": deal_values}})
    deal_id = None
    if status in (200, 201):
        deal_id = resp["data"]["id"]["record_id"]
        results["deal_id"] = deal_id

    # STEP 5: Create Follow-up Task
    due = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT15:00:00.000000000Z")
    linked = [{"target_object": "people", "target_record_id": person_id}]
    if deal_id:
        linked.append({"target_object": "deals", "target_record_id": deal_id})

    attio_request("POST", "/tasks", {
        "data": {
            "content": f"Follow up with {first} {last} — {property_name} website lead ({city}). Message: \"{message}\"",
            "format": "plaintext",
            "deadline_at": due,
            "is_completed": False,
            "assignees": [{"referenced_actor_type": "workspace-member", "referenced_actor_id": WORKSPACE_MEMBER_ID}],
            "linked_records": linked
        }
    })

    results["success"] = True
    return results


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


@app.route("/api/submit-lead", methods=["POST"], strict_slashes=False)
def submit_lead():
    try:
        # Rate limit before any parsing — cheapest rejection first.
        ip = (request.headers.get("x-forwarded-for", "") or request.remote_addr or "?").split(",")[0].strip()
        if rate_limited(ip):
            print(f"[lead] rate-limited ip={ip}")
            return _cors(jsonify({"success": False, "error": "Too many requests. Please email info@opamenities.com or call (720) 828-2170."})), 429

        try:
            data = request.get_json(force=True)
        except Exception:
            return _cors(jsonify({"success": False, "error": "Invalid request."})), 400

        clean, err = validate_payload(data or {})
        if err == "missing":
            return _cors(jsonify({"success": False, "error": "Please fill in the required fields."})), 400
        if err == "email":
            return _cors(jsonify({"success": False, "error": "Please enter a valid email address."})), 400
        if err:
            return _cors(jsonify({"success": False, "error": "Invalid request."})), 400

        # Honeypot: bots fill the hidden field. Pretend success; write nothing.
        if clean.get("company_website"):
            print("[lead] honeypot tripped — dropping submission")
            return _cors(jsonify({"success": True, "message": "Thank you! We'll be in touch within 24 hours."})), 200

        # Time-trap + JS token: same fake-success philosophy.
        verdict = bot_verdict(clean)
        if verdict:
            print(f"[lead] bot verdict={verdict} — dropping submission")
            return _cors(jsonify({"success": True, "message": "Thank you! We'll be in touch within 24 hours."})), 200
        if not clean.get("ts"):
            print("[lead] warn: submission without ts/tk (grace-accepted)")

        # Idempotency: double-click / repeat within 10 min — succeed without a second CRM write.
        if duplicate_lead(clean):
            print(f"[lead] duplicate suppressed: {clean['email']} / {clean['property_name']}")
            return _cors(jsonify({"success": True, "message": "Thank you! We'll be in touch within 24 hours."})), 200

        result = create_attio_lead(clean)

        if result.get("success"):
            print(f"[lead] created: person={result.get('person_id','?')} deal={result.get('deal_id','?')}")
            return _cors(jsonify({"success": True, "message": "Thank you! We'll be in touch within 24 hours."})), 200
        else:
            print(f"[lead] CRM error at step={result.get('step')}: {result.get('error')}")
            return _cors(jsonify({"success": False, "error": "We had trouble saving your request. Please email info@opamenities.com or call (720) 828-2170."})), 500

    except Exception as e:
        print(f"[lead] unhandled error: {type(e).__name__}: {e}")
        return _cors(jsonify({"success": False, "error": "Something went wrong. Please email info@opamenities.com or call (720) 828-2170."})), 500
