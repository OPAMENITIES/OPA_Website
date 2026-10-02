#!/usr/bin/env python3
"""OPA blog publishing pipeline (moved into the repo 2026-10-02; replaces the
build-master _gen_blog.py, which wrote to a stale OneDrive copy).

Source of truth: posts/<slug>.md (frontmatter + markdown body). posts/ is in
.vercelignore, so the sources are never served.

Frontmatter: title, slug, date, updated, category, description, image,
image_tag (real|render), image_alt. Optional:
  seo_title    <title> when it should differ from the H1 (og:title keeps the H1)
  redirect_to  post was folded into a money page by the 2026-09-01 SEO rescue;
               no page or md variant is built, index/llms link to the target,
               sitemap drops it (the 301 itself lives in vercel.json)
  generated    false = page and md variant are hand-built; registries only
  related      slug,slug  pins the two "Keep reading" cards

One command updates: post pages, md/ agent variants, blog index grid, sitemap,
llms.txt Posts section, middleware.js VALID + MD maps, vercel.json post
redirect + Vary:Accept rule, then reruns build_csp.py (which owns CSP).

Usage:  python scripts/gen_blog.py [--only slug1,slug2]
        (--only limits which post PAGES are written; registries always cover all posts)
"""
import re, json, sys, os, subprocess

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(S, "posts")
ORIGIN = "https://opamenities.com"
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

only = None
if "--only" in sys.argv:
    only = set(sys.argv[sys.argv.index("--only") + 1].split(","))

def read(p): return open(p, encoding="utf-8").read()
def write(p, s):
    # keep the file's existing line endings (a Windows autocrlf checkout is CRLF)
    nl = "\r\n" if os.path.exists(p) and b"\r\n" in open(p, "rb").read() else "\n"
    open(p, "w", encoding="utf-8", newline=nl).write(s)

# ---------------- parse posts ----------------
def parse_post(path):
    raw = read(path)
    m = re.match(r'---\n([\s\S]*?)\n---\n', raw)
    fm = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    fm["body"] = raw[m.end():].strip()
    fm["words"] = len(re.sub(r'[#*\[\]()>-]', ' ', fm["body"]).split())
    fm["mins"] = max(1, round(fm["words"] / 220))
    fm.setdefault("updated", fm["date"])
    fm.setdefault("seo_title", fm["title"])
    fm["built"] = "redirect_to" not in fm and fm.get("generated", "true") != "false"
    fm["href"] = fm.get("redirect_to", "/%s/" % fm["slug"])
    return fm

posts = sorted((parse_post(os.path.join(POSTS, f)) for f in os.listdir(POSTS) if f.endswith(".md")),
               key=lambda p: p["date"], reverse=True)
by_slug = {p["slug"]: p for p in posts}
slugs = [p["slug"] for p in posts]
live = [p for p in posts if "redirect_to" not in p]

# ---------------- markdown -> html ----------------
def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def attr(s): return esc(s).replace('"', "&quot;")

def inline(s):
    s = esc(s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', s)
    return s

def md_html(body):
    out = []
    for block in re.split(r'\n\s*\n', body):
        b = block.strip()
        if not b: continue
        if b.startswith("### "): out.append("<h3>%s</h3>" % inline(b[4:]))
        elif b.startswith("## "): out.append("<h2>%s</h2>" % inline(b[3:]))
        elif re.match(r'!\[[^\]]*\]\([^)]+\)$', b):
            m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)$', b)
            out.append('<figure class="afig"><img src="%s" alt="%s" loading="lazy"></figure>' % (m.group(2), attr(m.group(1))))
        elif all(l.lstrip().startswith("- ") for l in b.splitlines()):
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % inline(l.lstrip()[2:]) for l in b.splitlines()))
        elif all(re.match(r'\d+\.\s', l.lstrip()) for l in b.splitlines()):
            out.append("<ol>%s</ol>" % "".join("<li>%s</li>" % inline(re.sub(r'^\d+\.\s', '', l.lstrip())) for l in b.splitlines()))
        elif all(l.startswith("> ") or l == ">" for l in b.splitlines()):
            out.append("<blockquote><p>%s</p></blockquote>" % inline(" ".join(l[2:] for l in b.splitlines() if len(l) > 2)))
        else:
            out.append("<p>%s</p>" % inline(re.sub(r'\s*\n\s*', ' ', b)))
    return "\n".join(out)

# ---------------- post page template ----------------
# The template is a live post page, not a string in this script: every sitewide
# edit (brand lock, a11y, fonts, CTA wording) lands in the post pages too, so
# reusing one carries those edits forward. Only post-specific parts are swapped.
def template_page():
    for q in posts:
        path = os.path.join(S, q["slug"], "index.html")
        if q["built"] and os.path.exists(path):
            return q["slug"], read(path)
    sys.exit("FATAL: no generator-built post page on disk to use as the template")

def hl_title(title):
    t = esc(title)
    ws = t.split(" ")
    n = 3 if len(ws) > 5 else (2 if len(ws) > 3 else 1)
    return " ".join(ws[:-n]) + ' <span class="hl">' + " ".join(ws[-n:]) + "</span>"

def dotdate(d): return d.replace("-", ".")
def longdate(d):
    y, m, dd = d.split("-")
    return "%s %d, %s" % (MONTHS[int(m) - 1], int(dd), y)

def related_for(p):
    if "related" in p:
        return [by_slug[s.strip()] for s in p["related"].split(",")]
    same = [q for q in posts if q["slug"] != p["slug"] and q["category"] == p["category"]]
    rest = [q for q in posts if q["slug"] != p["slug"] and q not in same]
    return (same + rest)[:2]

def build_post(p, tpl_slug, shell):
    url = "%s/%s/" % (ORIGIN, p["slug"])
    schema = json.dumps({"@context": "https://schema.org", "@graph": [
        {"@type": "BlogPosting", "@id": url + "#article", "headline": p["title"],
         "description": p["description"], "image": ORIGIN + p["image"],
         "datePublished": p["date"], "dateModified": p["updated"],
         "author": {"@type": "Person", "name": "Justin", "jobTitle": "Owner",
                    "url": ORIGIN + "/about/", "worksFor": {"@id": ORIGIN + "/#organization"}},
         "publisher": {"@id": ORIGIN + "/#organization"},
         "mainEntityOfPage": url, "articleSection": p["category"],
         "wordCount": p["words"], "inLanguage": "en-US"},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": ORIGIN + "/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": ORIGIN + "/blog/"},
            {"@type": "ListItem", "position": 3, "name": p["title"], "item": url}]},
        {"@type": "WebPage", "@id": url, "name": p["title"], "url": url,
         "isPartOf": {"@id": ORIGIN + "/#website"}, "about": {"@id": ORIGIN + "/#organization"},
         "inLanguage": "en-US"}]}, ensure_ascii=False, separators=(",", ":"))

    rel = "".join(
        '<a class="rcard" href="%s"><span class="cat2">%s &middot; %s</span><h3>%s</h3>'
        '<span class="rd2">Read the post <svg class="ic"><use href="#i-arrow"/></svg></span></a>'
        % (q["href"], esc(q["category"]), longdate(q["date"]), esc(q["title"])) for q in related_for(p))

    upd = " &middot; updated %s" % dotdate(p["updated"]) if p["updated"] != p["date"] else ""
    tagcls = "real" if p.get("image_tag", "real") == "real" else ""
    taglbl = "our install" if tagcls else "concept render"
    lead = '<figure class="lead"><img src="%s" alt="%s" fetchpriority="high"><span class="ptag %s">%s</span></figure>' % (
        p["image"], attr(p.get("image_alt", p["title"])), tagcls, taglbl)

    t = shell
    def sub(pat, val):
        nonlocal t
        t, n = re.subn(pat, lambda m: val, t, count=1)
        if n != 1: sys.exit("FATAL: template slot not found: " + pat)
    sub(r"<title>[\s\S]*?</title>", "<title>" + attr(p["seo_title"]) + " | On Point Amenities</title>")
    sub(r'<meta name="description" content="[^"]*">', '<meta name="description" content="' + attr(p["description"]) + '">')
    sub(r'<link rel="canonical" href="[^"]*">', '<link rel="canonical" href="' + url + '">')
    sub(r'<meta property="og:title" content="[^"]*">', '<meta property="og:title" content="' + attr(p["title"]) + '">')
    sub(r'<meta property="og:description" content="[^"]*">', '<meta property="og:description" content="' + attr(p["description"]) + '">')
    sub(r'<meta property="og:url" content="[^"]*">', '<meta property="og:url" content="' + url + '">')
    sub(r'<meta property="og:image" content="[^"]*">', '<meta property="og:image" content="' + ORIGIN + p["image"] + '">')
    sub(r'<script type="application/ld\+json">[\s\S]*?</script>', '<script type="application/ld+json">' + schema + "</script>")
    sub(r'(?<=<a href="/blog/">Blog</a> &rsaquo; <b>)[^<]*(?=</b>)', esc(p["category"]))
    sub(r'<h1>[\s\S]*?</h1>', "<h1>" + hl_title(p["title"]) + "</h1>")
    sub(r'<div class="pmeta">[\s\S]*?</div>', '<div class="pmeta">%s%s &middot; %s min read &middot; by <b>Justin, owner</b></div>' % (dotdate(p["date"]), upd, p["mins"]))
    sub(r'<figure class="lead">[\s\S]*?</figure>', lead)
    sub(r'(?<=<div class="abody">\n)[\s\S]*?(?=\n  </div>\n  <div class="author">)', md_html(p["body"]))
    sub(r'(?<=<div class="rgrid">)[\s\S]*?(?=</div>\n</div></section>)', rel)
    # Leak guard: the template post's absolute URL only lives in slotted head
    # fields, so finding it in another post means an unslotted value carried over.
    if p["slug"] != tpl_slug and "%s/%s/" % (ORIGIN, tpl_slug) in t:
        sys.exit("FATAL: template post's URL leaked into " + p["slug"] + " (unslotted field)")
    os.makedirs(os.path.join(S, p["slug"]), exist_ok=True)
    write(os.path.join(S, p["slug"], "index.html"), t)
    return len(t)

# ---------------- md agent variant ----------------
def build_md(p):
    body = re.sub(r'\]\((/[^)]*)\)', lambda m: "](%s%s)" % (ORIGIN, m.group(1)), p["body"])
    upd = (", updated %s" % p["updated"]) if p["updated"] != p["date"] else ""
    txt = (
        "# %s — On Point Amenities\n\n"
        "> Markdown version of %s/%s/ — served via `Accept: text/markdown` content negotiation. "
        "Published %s%s. Category: %s. By Justin, owner of On Point Amenities.\n\n%s\n\n"
        "## Get started\n\n"
        "Book a free assessment: %s/contact/ · Phone: +1-720-828-2170 (owner-direct) · Email: info@opamenities.com\n"
        % (p["title"], ORIGIN, p["slug"], p["date"], upd, p["category"], body, ORIGIN))
    write(os.path.join(S, "md", "post-%s.md" % p["slug"]), txt)

# ---------------- registries ----------------
def upd_blog_index():
    p = os.path.join(S, "blog", "index.html")
    cards = "".join(
        '<a class="bcard" href="%s"><span class="cat">%s &middot; %s</span><h2>%s</h2>'
        '<span class="rd">Read the post <svg class="ic"><use href="#i-arrow"/></svg></span></a>'
        % (q["href"], esc(q["category"]), longdate(q["date"]), esc(q["title"])) for q in posts)
    h = read(p)
    write(p, re.sub(r'<div class="bgrid">[\s\S]*?</div>', lambda m: '<div class="bgrid">' + cards + "</div>", h, count=1))

def stable_order(existing):
    # keep the current order so a run with no new posts is a no-op; new slugs go on the end
    return [s for s in existing if s in slugs] + [s for s in slugs if s not in existing]

def upd_middleware():
    p = os.path.join(S, "middleware.js")
    h = read(p)
    seg = re.search(r'// __POSTS_START__[^\n]*\n([\s\S]*?)  // __POSTS_END__', h).group(1)
    order = stable_order(re.findall(r"'/([^']+)/',", seg))
    block = "".join("  '/%s/',\n" % s for s in order)
    h = re.sub(r'(// __POSTS_START__[^\n]*\n)[\s\S]*?(  // __POSTS_END__)',
               lambda m: m.group(1) + block + m.group(2), h, count=1)
    mdblock = "".join("  '/%s/': 'post-%s',\n" % (s, s) for s in order)
    h = re.sub(r'(// __POSTS_MD_START__[^\n]*\n)[\s\S]*?(  // __POSTS_MD_END__)',
               lambda m: m.group(1) + mdblock + m.group(2), h, count=1)
    write(p, h)

def upd_vercel():
    p = os.path.join(S, "vercel.json")
    cfg = json.loads(read(p))
    # Bare-to-slash 308 for every live post, generated or hand-built. Redirected
    # posts are excluded: their own 301 to the money page handles the bare URL.
    gen = "|".join(sorted(q["slug"] for q in posts if "redirect_to" not in q))
    for r in cfg["redirects"]:
        if r["source"].startswith("/:post("):
            r["source"] = "/:post(%s)" % gen
    # Vary:Accept covers every post slug (md variants exist for all of them).
    # Only the Vary rule: the CSP rule on the same source belongs to build_csp.py.
    src = "/:post(%s)/" % "|".join(sorted(slugs))
    vary = [h for h in cfg["headers"] if h["source"].startswith("/:post(")
            and [x["key"] for x in h["headers"]] == ["Vary"]]
    for h in vary:
        h["source"] = src
    if not vary:
        idx = next(i for i, h in enumerate(cfg["headers"]) if h["source"].startswith("/md/"))
        cfg["headers"].insert(idx, {"source": src, "headers": [{"key": "Vary", "value": "Accept"}]})
    write(p, json.dumps(cfg, indent=2) + "\n")

def upd_sitemap():
    p = os.path.join(S, "sitemap.xml")
    h = read(p)
    entry = lambda s: r'([ \t]*)<url><loc>%s/%s/</loc><lastmod>[^<]*</lastmod></url>\n' % (re.escape(ORIGIN), re.escape(s))
    for q in posts:
        if "redirect_to" in q:
            h = re.sub(entry(q["slug"]), "", h)
    added = False
    for q in live:
        line = "<url><loc>%s/%s/</loc><lastmod>%s</lastmod></url>\n" % (ORIGIN, q["slug"], q["updated"])
        if re.search(entry(q["slug"]), h):    # update in place, keeping its indent
            h = re.sub(entry(q["slug"]), lambda m: m.group(1) + line, h, count=1)
        else:   # new post: slot it in right after /blog/, matching its indent
            h = re.sub(entry("blog"), lambda m: m.group(0) + m.group(1) + line, h, count=1)
            added = True
    if added:   # blog index changed only when the post set did
        newest = max(q["updated"] for q in live)
        h = re.sub(r'(<url><loc>%s/blog/</loc><lastmod>)[^<]*' % re.escape(ORIGIN),
                   lambda m: m.group(1) + newest, h, count=1)
    write(p, h)

def upd_llms():
    p = os.path.join(S, "llms.txt")
    lines = "".join("- [%s](%s%s) (%s)\n" % (q["title"], ORIGIN, q["href"], q["date"]) for q in posts)
    h = read(p)
    write(p, re.sub(r'(## Posts\n\n)[\s\S]*?(\n## )', lambda m: m.group(1) + lines + m.group(2), h, count=1))

# ---------------- run ----------------
tpl_slug, shell = template_page()
built = 0
for p in posts:
    if not p["built"] or (only and p["slug"] not in only): continue
    n = build_post(p, tpl_slug, shell); build_md(p); built += 1
    print("POST %-64s %6d bytes  %sw" % (p["slug"][:64], n, p["words"]))
upd_blog_index(); upd_middleware(); upd_vercel(); upd_sitemap(); upd_llms()
print("REGISTRIES OK — %d posts tracked, %d pages written" % (len(posts), built))
subprocess.run([sys.executable, os.path.join(S, "scripts", "build_csp.py")], check=True)
