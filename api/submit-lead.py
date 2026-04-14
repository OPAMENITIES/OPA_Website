"""
OnPoint Amenities — Lead Capture Serverless Function (Vercel)
Handles form submissions and creates records in Attio CRM:
  Person -> Company -> Property -> Deal (New Inbound Lead) -> Task (follow-up)
"""
import json
import os
import re
import datetime
import requests
from http.server import BaseHTTPRequestHandler

ATTIO_API_KEY = os.environ.get("ATTIO_API_KEY", "")
ATTIO_BASE = "https://api.attio.com/v2"
ATTIO_HEADERS = {
    "Authorization": f"Bearer {ATTIO_API_KEY}",
    "Content-Type": "application/json"
}
WORKSPACE_MEMBER_ID = "9877069d-f1a4-498e-a3aa-c2120d40317c"
STAGE_NEW_INBOUND = "7b741213-46db-44b4-a245-52f6ead33850"


def attio_post(path, payload):
    r = requests.post(f"{ATTIO_BASE}{path}", headers=ATTIO_HEADERS, json=payload, timeout=10)
    return r.status_code, r.json()

def attio_put(path, payload, params=None):
    r = requests.put(f"{ATTIO_BASE}{path}", headers=ATTIO_HEADERS, json=payload, params=params, timeout=10)
    return r.status_code, r.json()

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

    status, resp = attio_put(
        "/objects/people/records",
        {"data": {"values": person_values}},
        params={"matching_attribute": "email_addresses"}
    )
    if status not in (200, 201):
        return {"success": False, "error": f"Person creation failed: {resp.get('message', str(resp))}", "step": "person"}
    person_id = resp["data"]["id"]["record_id"]
    results["person_id"] = person_id

    # STEP 2: Create or find Company
    search_r = requests.post(
        f"{ATTIO_BASE}/objects/companies/records/query",
        headers=ATTIO_HEADERS,
        json={"filter": {"name": {"$eq": property_name}}, "limit": 1},
        timeout=10
    )
    if search_r.status_code == 200 and search_r.json().get("data"):
        company_id = search_r.json()["data"][0]["id"]["record_id"]
    else:
        status, resp = attio_post(
            "/objects/companies/records",
            {"data": {"values": {"name": [{"value": property_name}]}}}
        )
        if status not in (200, 201):
            return {"success": False, "error": f"Company creation failed: {resp.get('message', str(resp))}", "step": "company"}
        company_id = resp["data"]["id"]["record_id"]
    results["company_id"] = company_id

    # STEP 3: Upsert Property
    status, resp = attio_put(
        "/objects/properties/records",
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
        f"Source: Website Form\n"
        f"City: {city}\n"
        f"Property Type: {property_type}\n"
        f"Residents/Employees: {num_residents}\n"
        f"Message: {message}"
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

    status, resp = attio_post("/objects/deals/records", {"data": {"values": deal_values}})
    deal_id = None
    if status in (200, 201):
        deal_id = resp["data"]["id"]["record_id"]
        results["deal_id"] = deal_id

    # STEP 5: Create Follow-up Task
    due = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT15:00:00.000000000Z")
    linked = [{"target_object": "people", "target_record_id": person_id}]
    if deal_id:
        linked.append({"target_object": "deals", "target_record_id": deal_id})

    status, resp = attio_post("/tasks", {
        "data": {
            "content": f"Follow up with {first} {last} — {property_name} website lead ({city}). Message: \"{message}\"",
            "format": "plaintext",
            "deadline_at": due,
            "is_completed": False,
            "assignees": [{"referenced_actor_type": "workspace-member", "referenced_actor_id": WORKSPACE_MEMBER_ID}],
            "linked_records": linked
        }
    })
    if status in (200, 201):
        results["task_id"] = resp["data"]["id"]["task_id"]

    results["success"] = True
    return results


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
}


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler."""

    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
        except Exception:
            self._respond(400, {"success": False, "error": "Invalid JSON"})
            return

        required = ["first_name", "last_name", "email", "property_name", "city"]
        missing = [f for f in required if not data.get(f, "").strip()]
        if missing:
            self._respond(400, {"success": False, "error": f"Missing required fields: {', '.join(missing)}"})
            return

        result = create_attio_lead(data)

        if result.get("success"):
            self._respond(200, {
                "success": True,
                "message": "Thank you! We'll be in touch within 24 hours.",
                "ids": {k: v for k, v in result.items() if k.endswith("_id")}
            })
        else:
            self._respond(500, {
                "success": False,
                "error": "We received your message but had trouble saving it. We'll still follow up!"
            })

    def _respond(self, status_code, body_dict):
        body = json.dumps(body_dict).encode("utf-8")
        self.send_response(status_code)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # suppress default access log noise
