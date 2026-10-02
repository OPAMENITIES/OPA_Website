# opamenities.com — Live Site

**This repo is the production source for https://opamenities.com** (Vercel project `opa_website`, team *opa-cto's projects*). Every push to `master` auto-deploys.

## What this is
A static mirror of the former WordPress site (migrated off Vine Digital Studio / 365 Retail Markets hosting on 2026-08-21), plus:
- `/api/submit-lead.py` — serverless lead-capture endpoint (Flask). Creates Person → Company → Property → Deal → Task in **Attio CRM**. Requires `ATTIO_API_KEY` env var on the Vercel project. Wired to the form on `/contact/`.
- `sitemap.xml`, `robots.txt`, `llms.txt`, branded `404.html`, `vercel.json` (trailing slashes, legacy sitemap redirects, cache headers).
- Vercel Web Analytics script on all pages (enable in Vercel → project → Analytics).

## Branches
- `master` — the live static site.
- `legacy-spa-draft` — pre-migration single-page draft (kept for history; source of the lead API).

## History / context
- WordPress backup of record (incl. database `opamenities_wp_vbp6u.sql`): OPA archive, 2026-08-21.
- The multi-page rebuild (locked design system: Poppins/Lato, navy/green, SVG icons) will replace this mirror page-by-page on the same project. Docs live in the OPA_Website_Rebuild folder (strategy doc, sitemap diagram, prototype, styleguide, money pages).

## Editing
Change files → commit → push to `master` → live in ~30s. Keep URLs stable; 301 via `vercel.json` if a URL must change.

**This repo is the only source of truth (2026-10-02).** The OneDrive build master (`OPA_Website_Rebuild/2026.08.25_WEB_Homepage_Rebuild_v01/`) and its `_gen_*.py` scripts are retired: they predate the September brand-lock, a11y and security PRs, and running them would regenerate stale pages. The page generators were one-time scaffolds; the HTML in this repo is now edited directly.

## Publishing a blog post
1. Write `posts/<slug>.md` (frontmatter fields are documented at the top of `scripts/gen_blog.py`). `posts/` is in `.vercelignore`, so sources are never served.
2. Run `python scripts/gen_blog.py`. It builds the page (using the newest generated post page as the template, so sitewide edits carry over) and the `md/` variant, then updates the blog index, sitemap, `llms.txt`, `middleware.js` maps and the `vercel.json` post rules, and reruns `build_csp.py`.
3. Run `python scripts/verify_brand.py`, push to a preview branch, then run `python scripts/verify_agentic.py <preview-url>`.

With no post changes, a run is a no-op (zero diff). Regenerating a post re-wraps it in the newest post's page, so put post-specific edits in `posts/<slug>.md`; hand edits to a generated page outside the swapped slots are overwritten. Posts folded into money pages carry `redirect_to:`; hand-built posts carry `generated: false` and only appear in the registries.

## Content publishing standard (AI disclosure)
- **Sitewide:** every page's footer carries: "Some content on this site is created with the help of AI tools and reviewed by a human before publishing."
- **About page:** carries the "How We Work" AI-transparency section.
- **Every NEW blog post** must end with this line (before the footer):
  > *This post was drafted with AI and edited, fact-checked and approved by a human before publishing.*
  Existing posts (authored pre-migration by the previous agency) are exempt.

## Agentic/AEO layer (2026-08-25)

Added in response to the Is Agentic audit (baseline 76/100):

- **Markdown content negotiation** — `middleware.js` (Edge Middleware, runs before the filesystem) serves `/md/*.md` when a request carries `Accept: text/markdown` on `/`, `/about/`, `/services/`, `/businesses/`, `/contact/`, `/service-area/`, `/blog/`, `/privacy/`. HTML responses on those routes carry `Vary: Accept` (vercel.json). The `/md/` variants are `noindex` and must be kept in sync with page content edits.
- **Agent guidance** — `llms.txt` includes a "When to use On Point Amenities" section and markdown-access instructions.
- **404** — recovery links to core pages, `/sitemap.xml`, `/llms.txt`.
- **Schema** — homepage Organization JSON-LD carries contactPoint, address, sameAs, areaServed, telephone, email, description.
- **Trust pages** — `/privacy/` added (linked from every footer, in sitemap.xml).
- **Tests** — `scripts/verify_agentic.py` checks all of the above against production. Run after any deploy touching these files.
