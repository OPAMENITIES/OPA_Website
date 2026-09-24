#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the OPA brand lock and the 2026-09-06 audit fixes are still shipped.

Why this exists: the site has no build step and no partials — the header and
footer are inlined verbatim in every page. A page added from an old template
inherits none of the sitewide fixes and nothing catches it. PR #4 proved that:
it landed a page that predated PRs #3 and #5 and silently re-introduced the old
wordmark, both retired CTA wordings, and the unlogged fourth tagline.

Sources of truth:
  OPA Brand Lockup Standard, locked 2026-08-06  (brand/naming-and-tagline.md)
  OPA-Website-Audit-2026-09-06.md               (fixes 1-3)

Exit 0 when clean, 1 otherwise. Every failure is printed — the script does not
bail on the first, because a page pasted from an old template trips six at once
and you want them in one pass, not six.

Known gap this file deliberately covers rather than fixes: scripts/build_csp.py
hardcodes its NAV and BIZ page lists and only auto-discovers post directories,
so a new top-level or /businesses/ page is silently left out of the hash-based
CSP. check_csp_coverage() reads the shipped vercel.json and fails when a
templated page is not covered by a strict rule.
"""
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A page carrying the full site chrome is identified by the wordmark span. This
# marker is the thing the lock is actually about, so it cannot drift away from
# what we are checking. Note the real header markup is `class="wrap hdr-in"` —
# grepping for `class="hdr-in"` matches nothing and would silently pass.
TEMPLATE_MARKER = '<span class="wm">'

# Floor, not equality: a legitimately added page should raise this, and bumping
# it is the human moment where someone notices the page set grew. Below the
# floor means pages vanished or the marker drifted — either way, stop.
EXPECTED_TEMPLATED = 24

MD = u"\u2014"        # em dash, literal in these files
RS = u"&rsquo;"       # the site's apostrophe entity

WORDMARK = u'<span class="wm">On Point<small>Amenities</small></span>'
CTA = u"Book a Free Assessment"
TAGLINE = u"Stocked right, managed tight. That" + RS + u"s On Point."

# The bare hide rule audit fix 1 removed. Its presence *is* the regression.
OLD_NAV_RULE = u"@media(max-width:960px){.hdr nav{display:none}}"
NAV_CSS_MARKER = u"@media(max-width:620px){"

# The real Instagram handle is a URL, not a wordmark or a heading. Exempt the
# substring, never the file — a file-level exemption would wave through a
# genuine violation that lands in the same page later.
INSTAGRAM = u"instagram.com/onpointamenities"

BANNED = [
    u"OnPoint",                              # lock: never one word
    u"Smart Convenience, Always On Point.",  # the unlogged fourth tagline
    u"Book a Free Consultation",
    u"Book a Free On-Site Consultation",
    u"Request My Free Consultation",
    u"consultation",                         # one offer, one noun: "assessment"
    u"Request Your Free On-Site Assessment", # retired 2026-09-24 for the condensed CTA
    u"gets a real-time alert",               # alerts are offered on request, not by default
    u"AI-powered",                           # say what the equipment does, not "AI" (2026-09-24)
    u"AI-secured",
    u"AI-enabled",
]
CASE_INSENSITIVE = {u"consultation", u"Request Your Free On-Site Assessment",
                    u"AI-powered", u"AI-secured", u"AI-enabled"}

HOME_TITLE = (u"On Point Amenities " + MD + u" Fully Managed Micro Markets, "
              u"Smart Coolers &amp; Modern Vending | South Denver Metro")
HOME_REQUIRED = [
    u"<title>" + HOME_TITLE + u"</title>",
    u'<meta property="og:title" content="On Point Amenities ' + MD +
    u' Modern Convenience, Managed End-to-End">',
    u'<h1>Modern Convenience, <span class="hl">Managed End-to-End.</span></h1>',
    u"On Point Amenities delivers fully managed micro markets, smart coolers, "
    u"and modern cashless vending for South Denver Metro properties " + MD + u" "
    u"installed, stocked, and serviced end-to-end at zero upfront cost. "
    u"Veteran-owned. Book a free assessment.",
    u'<p class="sub">Fully managed micro markets, smart coolers, and modern '
    u"vending for South Denver Metro" + RS + u"s premium properties &mdash; so "
    u"your team never has to think about it.</p>",
]

SKIP_DIRS = {".git", "__pycache__", "node_modules"}

failures = []


def fail(msg):
    failures.append(msg)


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def walk(exts):
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            if os.path.splitext(name)[1] in exts:
                yield os.path.join(dirpath, name)


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------- discovery

def templated_pages():
    pages = [p for p in walk({".html"}) if TEMPLATE_MARKER in read(p)]
    if len(pages) < EXPECTED_TEMPLATED:
        fail("templated pages: found %d, expected at least %d — pages were "
             "removed, or the '%s' marker drifted and every per-page check "
             "below is running on the wrong set"
             % (len(pages), EXPECTED_TEMPLATED, TEMPLATE_MARKER))
    return pages


# ------------------------------------------------------------ banned copy

def check_banned():
    # brand/ holds the lock itself (naming-and-tagline.md), which has to quote
    # every banned string in order to ban it. It is internal (.vercelignore)
    # and never served, so it is the one path exempt from this check.
    lock_dir = os.path.join(ROOT, "brand") + os.sep
    paths = [p for p in walk({".html", ".md"}) if not p.startswith(lock_dir)]
    llms = os.path.join(ROOT, "llms.txt")
    if os.path.exists(llms):
        paths.append(llms)
    for path in paths:
        text = read(path)
        scrubbed = re.sub(re.escape(INSTAGRAM), u"", text, flags=re.IGNORECASE)
        for phrase in BANNED:
            hay = scrubbed.lower() if phrase in CASE_INSENSITIVE else scrubbed
            needle = phrase.lower() if phrase in CASE_INSENSITIVE else phrase
            n = hay.count(needle)
            if n:
                fail("%s: %d x banned %r" % (rel(path), n, phrase))
    return len(paths)


# ------------------------------------------------------------ CTA buttons

# The chrome check above only proves the CTA is on the page somewhere. Body
# buttons drifted anyway: by 2026-09-24 eleven of them said "Book the free
# walkthrough", "Book a walkthrough for your gym" and similar. Any link to the
# contact page, or any submit button, that reads like an ask must carry the
# one locked wording. Plain "Contact" nav links are not asks and pass.
ASK_WORDS = re.compile(r"\b(book|request|walkthrough|assessment|schedule|start)\b", re.I)
CONTACT_LINK = re.compile(
    r'<a\b[^>]*href="/contact/[^"]*"[^>]*>(.*?)</a>|<button\b[^>]*type="submit"[^>]*>(.*?)</button>',
    re.S)


def check_cta_buttons(pages):
    for path in pages:
        for m in CONTACT_LINK.finditer(read(path)):
            label = re.sub(r"<[^>]+>", u"", m.group(1) or m.group(2) or u"")
            label = u" ".join(label.split())
            if ASK_WORDS.search(label) and label != CTA:
                fail("%s: call-to-action reads %r, expected the locked %r"
                     % (rel(path), label, CTA))


# ------------------------------------------------------------------ fonts

# Justin ruled 2026-09-24: the site self-hosts its fonts (assets/fonts/). A
# page pasted from an old template brings the Google Fonts <link> back, and the
# strict CSP no longer allows it, so that page would silently fall back to
# system fonts. The WordPress uploads under wp-content/ are the one exception.
LEGACY_WP_DIRS = ("wp-content/", "wp-includes/")


def check_fonts():
    for path in walk({".html"}):
        r = rel(path)
        if r.startswith(LEGACY_WP_DIRS):
            continue
        text = read(path)
        for host in (u"fonts.googleapis.com", u"fonts.gstatic.com"):
            if host in text:
                fail("%s: loads %s; fonts are self-hosted in assets/fonts/" % (r, host))
        for url in set(re.findall(r"/assets/fonts/[\w.-]+\.woff2", text)):
            if not os.path.exists(os.path.join(ROOT, url.lstrip("/"))):
                fail("%s: references missing font file %s" % (r, url))


# --------------------------------------------------------------- homepage

def check_homepage():
    path = os.path.join(ROOT, "index.html")
    text = read(path)
    for req in HOME_REQUIRED:
        if req not in text:
            fail("index.html: missing locked copy %r" % (req[:70] + "...",))

    # The JSON-LD WebPage name must mirror <title>. #4 rewrote the title and
    # left the structured-data name on the old string, so the page shipped a
    # headline and a machine-readable name that disagreed. Derived from the
    # live <title> rather than pinned, so a deliberate retitle stays legal.
    m = re.search(r"<title>(.*?)</title>", text, re.S)
    if not m:
        fail("index.html: no <title>")
        return
    expected = m.group(1).replace(u"&amp;", u"&")
    if u'"name":"%s"' % expected not in text:
        fail("index.html: JSON-LD WebPage name does not match <title> "
             "(expected \"name\":%r)" % expected)


# --------------------------------------------------------- per-page chrome

def check_pages(pages):
    for path in pages:
        text = read(path)
        r = rel(path)
        if text.count(WORDMARK) != 2:
            fail("%s: %d x corrected wordmark, expected 2 (header + footer)"
                 % (r, text.count(WORDMARK)))
        if text.count(u'class="navtoggle"') != 1:
            fail("%s: %d x navtoggle button, expected 1 (audit fix 1)"
                 % (r, text.count(u'class="navtoggle"')))
        if text.count(u'id="primary-nav"') != 1:
            fail("%s: %d x id=\"primary-nav\", expected 1" % (r, text.count(u'id="primary-nav"')))
        if CTA not in text:
            fail("%s: missing the one locked CTA wording %r" % (r, CTA))
        if text.count(TAGLINE) != 1:
            fail("%s: %d x locked footer tagline, expected 1" % (r, text.count(TAGLINE)))
        if OLD_NAV_RULE in text:
            fail("%s: still ships the bare mobile-nav hide rule — this page "
                 "predates audit fix 1" % r)
        if NAV_CSS_MARKER not in text:
            fail("%s: missing the <=620px header CSS from audit fix 1" % r)


# -------------------------------------------------------------- structured

def check_jsonld():
    total = 0
    for path in walk({".html"}):
        for m in re.finditer(
                r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
                read(path)):
            total += 1
            try:
                json.loads(m.group(1))
            except ValueError as exc:
                fail("%s: ld+json block %d does not parse — %s"
                     % (rel(path), total, exc))
    return total


# --------------------------------------------------------------------- CSP

def csp_covered_files():
    """Pages reached by a strict (hash-based) CSP rule in the shipped config.

    Derived from vercel.json rather than from build_csp.py's page list, so the
    check measures what is actually served and stays honest about that script's
    hardcoded NAV/BIZ lists.
    """
    cfg = json.loads(read(os.path.join(ROOT, "vercel.json")))
    covered = set()
    for rule in cfg.get("headers", []):
        values = [h["value"] for h in rule["headers"]
                  if h["key"] == "Content-Security-Policy"]
        # "Strict" means the script-src is hash-pinned. Do NOT test for the
        # absence of 'unsafe-inline': every policy here carries it in
        # style-src, so that test silently matches nothing.
        if not values or u"'sha256-" not in values[0]:
            continue
        src = rule["source"]
        if src == "/":
            covered.add("index.html")
            continue
        m = re.match(r"^/((?:[\w-]+/)*):\w+\(([^)]*)\)/$", src)
        if m:
            covered.update(m.group(1) + alt + "/index.html"
                           for alt in m.group(2).split("|"))
    return covered


def check_csp_coverage(pages):
    covered = csp_covered_files()
    if not covered:
        fail("vercel.json: no strict CSP rules found — the whole coverage "
             "check just passed vacuously")
        return 0
    for path in pages:
        if rel(path) not in covered:
            fail("%s: not covered by any strict CSP rule. build_csp.py "
                 "hardcodes NAV and BIZ, so a new top-level or /businesses/ "
                 "page must be added to those lists by hand." % rel(path))
    return len(covered)


def check_csp_fresh():
    """vercel.json must be exactly what build_csp.py regenerates.

    Regenerate and diff rather than re-deriving the hashes here: duplicating
    the generator would let the two drift apart and agree with each other.
    """
    vp = os.path.join(ROOT, "vercel.json")
    with open(vp, "rb") as fh:
        before = fh.read()
    try:
        # The child prints an em dash; force UTF-8 both ways so it does not
        # come back as U+FFFD through the Windows console codepage.
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "build_csp.py")],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        if proc.returncode != 0:
            fail("scripts/build_csp.py exited %d:\n%s"
                 % (proc.returncode, proc.stdout.decode("utf-8", "replace").strip()))
            return None
        with open(vp, "rb") as fh:
            after = fh.read()
        if before != after:
            fail("vercel.json is stale — run `python scripts/build_csp.py` and "
                 "commit the result. Inline <script> content changed without "
                 "the hashes being regenerated, so the shipped CSP blocks it.")
        return proc.stdout.decode("utf-8", "replace").strip()
    finally:
        with open(vp, "wb") as fh:
            fh.write(before)


# -------------------------------------------------------------------- main

def main():
    # Findings quote page copy, which is not all cp1252-encodable.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    pages = templated_pages()
    scanned = check_banned()
    check_homepage()
    check_pages(pages)
    check_cta_buttons(pages)
    check_fonts()
    blocks = check_jsonld()
    covered = check_csp_coverage(pages)
    csp_line = check_csp_fresh()

    print("templated pages   : %d" % len(pages))
    print("files scanned     : %d" % scanned)
    print("ld+json blocks    : %d" % blocks)
    print("strict-CSP pages  : %d" % covered)
    if csp_line:
        print("build_csp.py      : %s" % csp_line)

    if failures:
        print("\n%d FAILURE(S):" % len(failures))
        for msg in failures:
            print("  - %s" % msg)
        return 1
    print("\nOK — brand lock and the 2026-09-06 audit fixes are intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
