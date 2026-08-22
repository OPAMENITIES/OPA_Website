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
