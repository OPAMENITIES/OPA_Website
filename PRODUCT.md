# Product

<!-- impeccable:product-schema 1 -->

opamenities.com is the public marketing site for On Point Amenities (OPA). It is the live repo `OPAMENITIES/OPA_Website` on the `master` branch, which Vercel deploys on push. The old `C:\Dev\OPA_Website-master` folder is a stale ZIP export and deploys nowhere.

## Platform

web

## Users

Decision-makers at locations that could host machines: property managers (multifamily), facilities managers, and HR/workplace managers, plus owners and managers at gyms, hotels, healthcare facilities and auto dealerships. They are busy and don't want another vendor to babysit. Their job on the site is to decide whether OPA is worth a 20-minute walkthrough.

## Product Purpose

Turn a qualified local location into a booked walkthrough or a direct call with the owner. Success means qualified contact from inside the service area, through `/contact/`, the lead form (`api/submit-lead.py` → Attio), phone or email.

## Positioning

- **Local and owner-run:** fully managed smart coolers, micro markets, smart stores and modern vending, installed and run by a local, veteran- and family-owned operator in Castle Rock. You work directly with the owner.
- **Premium on purpose:** the route is kept tight on purpose, and OPA will say so when a location isn't a fit.
- **Screen as a feature:** the machine's header screen carries the location's own promos. This is live at Castle Rock Autoplex and at a Castle Rock gym.

## Operating Context

- **Service area:** Arapahoe, Douglas, Denver and Jefferson counties ("South Denver Metro"). Cities named on the site include Aurora, Centennial, Lone Tree, Parker, Highlands Ranch, Littleton, Lakewood, Arvada and Castle Rock.
- **Process:** free 20-minute walkthrough → a straight answer → install 4–8 weeks after signing → OPA runs it.
- **Verticals:** multifamily, offices, gyms and fitness, hotels and hospitality, healthcare, auto dealerships (`/businesses/*`).
- **Contact:** owner-direct phone +1-720-828-2170, info@opamenities.com.

## Capabilities and Constraints

Service claims confirmed by the owner on 2026-09-23:

- $0 to the location for equipment, install, stocking and service.
- Monitored 24/7.
- **Next-day** service response.
- Same-day fixes when an order goes wrong.
- Restocked often, multiple times per week.
- 100% cashless.

- **Real-time alerts** are offered, but only switched on after they are discussed with the client (Justin, 2026-09-24). Copy may say they are available; never describe them as on by default.
- "If your building is on this map, I can be standing in front of your machine today" (Service area) refers to the assessment visit, not service response, so it does not conflict with next-day response (Justin, 2026-09-24).

Not verified; don't reuse these as evidence until confirmed:

- "locally sourced options" (About). Removed from `md/about.md` 2026-09-24; no longer on the site.
- "AI" equipment labels (AI followed by powered, secured or enabled), on Services and elsewhere. Justin ruled 2026-09-24: describe what the equipment does (locked until you tap, charges only for what you take), with no "AI" label. Reworded sitewide.
- leftover agency SEO copy on the services and service-area pages

Stack and deploy:

- Static multi-page HTML/CSS (mirrored from the old WordPress site).
- A Python/Flask serverless lead endpoint, and Edge `middleware.js` that serves `/md/*.md`.
- `vercel.json` for redirects and headers.
- No build step and no dev script: use `vercel dev` or any static server.
- `scripts/verify_agentic.py` checks production.
- A multi-page rebuild with a locked design system is planned (OPA_Website_Rebuild).

## Brand Commitments

- **Name:** On Point Amenities / "On Point". **Never joined into one word**, including in alt text (full Never list in the naming lock). The only allowed lowercase form is the Instagram handle URL `instagram.com/onpointamenities`.
- **Naming lock:** [`brand/naming-and-tagline.md`](brand/naming-and-tagline.md) is the single source for the brand's own words: tagline, hero H1, CTA, the Never list. It was rebuilt 2026-09-23; the original is lost. `scripts/verify_brand.py` enforces it in CI.
- **Voice** (`opa-brand-voice` skill): calm first, clear second, smart third. Caregiver archetype with Sage secondary. A reliable operations partner, not a vendor. No hype.
- **Required:** the AI-disclosure footer on every page, and a disclosure line at the end of every new blog post (README).
- **Identity:** veteran- and family-owned, founded 2024, based in Castle Rock, CO. Owner Justin Krakow.

## Evidence on Hand

- **Case study:** Castle Rock Autoplex (second contract within 48 hours), with an owner quote.
- **Lead magnet:** `/audit` → `assets/5-minute-amenity-audit.pdf`.
- **Media:** real photos, videos and logos in `assets/`.
- **Absent:** no other named customers, no other testimonials, and no placement or revenue numbers. Never invent them.

## Product Principles

1. **Straight answers.** Say plainly whether a location is a fit, and never oversell.
2. **Local and owner-direct.** The owner's name, phone and service area are part of the offer, not the footer.
3. **Low effort for the location.** Every page shows that OPA takes the work off the manager's plate.
4. **Claims stay honest.** Publish only what the owner has confirmed, and fix copy that contradicts the confirmed facts.

## Accessibility & Inclusion

No product-specific standard has been named. Use WCAG 2.2 AA as the working baseline for a public site.
