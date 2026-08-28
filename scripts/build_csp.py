#!/usr/bin/env python3
"""Build Content-Security-Policy headers for vercel.json.

Strict policy (hash-based script-src, no unsafe-inline) on all new-system pages;
moderate policy on legacy WP category/tag pages (inline handlers require it).
Rerun after ANY change to inline <script> content on new-system pages, then
redeploy. JSON-LD data blocks are ignored (not executable).
"""
import re, os, json, hashlib, base64, sys

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NAV = ["about", "blog", "businesses", "contact", "privacy", "service-area", "services", "thank-you"]
BIZ = ["multifamily", "dealerships", "gyms", "offices", "hospitality", "healthcare"]
posts = sorted(d for d in os.listdir(S) if os.path.isdir(os.path.join(S, d))
               and os.path.exists(os.path.join(S, d, "index.html"))
               and d not in NAV + ["category", "tag", "api", "assets", "md", "scripts",
                                    "wp-content", "wp-includes", "businesses", "__pycache__"])

pages = [os.path.join(S, "index.html")] + \
        [os.path.join(S, p, "index.html") for p in NAV] + \
        [os.path.join(S, "businesses", b, "index.html") for b in BIZ] + \
        [os.path.join(S, p, "index.html") for p in posts]

hashes, seen = [], set()
for path in pages:
    h = open(path, encoding="utf-8").read()
    for m in re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', h):
        attrs, body = m.group(1), m.group(2)
        if "src=" in attrs: continue
        if "ld+json" in attrs: continue          # data block, not executable
        dig = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
        if dig not in seen:
            seen.add(dig); hashes.append(dig)
    if re.search(r'\son[a-z]+\s*=', h):
        sys.exit("FATAL: inline event handler found in strict-CSP page: " + path)

GA_S = "https://www.googletagmanager.com"
GA_C = "https://*.google-analytics.com https://*.analytics.google.com https://www.googletagmanager.com https://stats.g.doubleclick.net"

def policy(script_src):
    return ("default-src 'self'; script-src %s; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: %s %s; media-src 'self'; "
            "connect-src 'self' %s; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'self'"
            % (script_src, GA_S, GA_C, GA_C))

strict = policy("'self' %s %s" % (GA_S, " ".join("'sha256-%s'" % d for d in hashes)))
loose = policy("'self' 'unsafe-inline' %s" % GA_S)

post_alt = "|".join(sorted(posts))
strict_sources = ["/", "/:page(%s)/" % "|".join(NAV), "/businesses/:page(%s)/" % "|".join(BIZ), "/:post(%s)/" % post_alt]
loose_sources = ["/category/:slug/", "/tag/:slug/"]

vp = os.path.join(S, "vercel.json")
cfg = json.load(open(vp, encoding="utf-8"))
# drop previous CSP-only rules, then append current ones
cfg["headers"] = [r for r in cfg["headers"]
                  if not (len(r["headers"]) == 1 and r["headers"][0]["key"] == "Content-Security-Policy")]
for src in strict_sources:
    cfg["headers"].append({"source": src, "headers": [{"key": "Content-Security-Policy", "value": strict}]})
for src in loose_sources:
    cfg["headers"].append({"source": src, "headers": [{"key": "Content-Security-Policy", "value": loose}]})
open(vp, "w", encoding="utf-8").write(json.dumps(cfg, indent=2) + "\n")
print("CSP OK — %d unique inline-script hashes across %d pages; %d strict + %d loose rules"
      % (len(hashes), len(pages), len(strict_sources), len(loose_sources)))
