#!/usr/bin/env python3
"""Agentic/AEO readiness checks for opamenities.com.

Run after every deploy that touches vercel.json, llms.txt, /md/*, /privacy/,
404.html, or homepage JSON-LD:  python3 scripts/verify_agentic.py [base_url]

Covers the Is Agentic audit items (2026-08-25): 404 recovery body, markdown
content negotiation + Vary, llms.txt when-to-use, Organization schema
completeness, trust pages. Exits non-zero on any failure.
"""
import json, re, sys, urllib.request, urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://opamenities.com"
MD_PAGES = ["", "about", "services", "businesses", "contact", "service-area", "blog", "privacy"]
FAILS = []

def fetch(path, accept=None, redirect=True):
    url = BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": "opa-verify/1.0",
                                               **({"Accept": accept} if accept else {})})
    opener = urllib.request.build_opener() if redirect else urllib.request.build_opener(
        type("NR", (urllib.request.HTTPRedirectHandler,),
             {"redirect_request": lambda *a, **k: None})())
    try:
        with opener.open(req, timeout=25) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "ignore")

def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)

# 1. Agent-friendly 404 with recovery links
s, h, b = fetch("/some-path-that-does-not-exist/")
check("404 status on nonexistent path", s == 404, f"got {s}")
check("404 body has recovery links", all(x in b for x in ["/sitemap.xml", "/llms.txt", "/contact/", "/services/"]))
# Audit's exact test: bare path, no redirect following, default Accept -> must be a direct 404
s, h, b = fetch("/some-path-that-does-not-exist", redirect=False)
check("bare-path direct 404 for agents (no 308)", s == 404, f"got {s}")
check("agent 404 is markdown w/ recovery body",
      "markdown" in h.get("Content-Type", "") and "sitemap.xml" in b and "llms.txt" in b,
      f"ct {h.get('Content-Type')}")
# Browsers must keep the branded HTML 404 flow
s, h, b = fetch("/some-path-that-does-not-exist/", accept="text/html,application/xhtml+xml")
check("browser 404 still HTML", s == 404 and "<html" in b.lower(), f"status {s}")
# A real page requested curl-style must NOT 404
s, h, b = fetch("/about", redirect=False)
check("bare valid path passes through (308 or 200)", s in (200, 308), f"got {s}")

# 2+3. Markdown content negotiation with Vary: Accept
for p in MD_PAGES:
    path = "/" + (p + "/" if p else "")
    s, h, b = fetch(path, accept="text/markdown")
    ct, vary = h.get("Content-Type", ""), h.get("Vary", "")
    check(f"md negotiation {path}", s == 200 and "markdown" in ct and b.lstrip().startswith("#"),
          f"status {s}, ct {ct}")
    check(f"Vary: Accept on {path}", "Accept" in vary, f"vary {vary!r}")
    s2, h2, _ = fetch(path)  # default request must still be HTML
    check(f"html default {path}", s2 == 200 and "text/html" in h2.get("Content-Type", ""))

# 4. llms.txt when-to-use guidance
s, h, b = fetch("/llms.txt")
check("llms.txt reachable", s == 200)
check("llms.txt when-to-use section", "When to use On Point Amenities" in b and "How to act" in b)

# 5+7. Organization JSON-LD completeness on homepage
s, h, b = fetch("/")
org = None
for m in re.finditer(r'<script type="application/ld\+json"[^>]*>([\s\S]*?)</script>', b):
    try:
        g = json.loads(m.group(1))
        for n in g.get("@graph", [g]):
            t = n.get("@type")
            types = t if isinstance(t, list) else [t]
            if "Organization" in types:
                org = n
    except ValueError:
        pass
check("Organization JSON-LD present", org is not None)
if org:
    for k in ["contactPoint", "address", "sameAs", "url", "logo", "description", "telephone", "email"]:
        check(f"Organization.{k}", k in org)

# 6. Trust pages: /about/, /contact/, /privacy/ each 200 with substance
for p in ["/about/", "/contact/", "/privacy/"]:
    s, h, b = fetch(p)
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[\s\S]*?</\1>", "", b))
    check(f"trust page {p}", s == 200 and len(re.sub(r"\s+", " ", text)) > 500, f"status {s}")

# sitemap includes privacy
s, h, b = fetch("/sitemap.xml")
check("sitemap includes /privacy/", "/privacy/" in b)

print(f"\n{'ALL CHECKS PASSED' if not FAILS else str(len(FAILS)) + ' FAILURES: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
