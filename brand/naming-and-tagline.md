# On Point Amenities — Naming & Tagline Lock

> **Status:** Rebuilt 2026-09-23 from the strings enforced by `scripts/verify_brand.py` and the OPA vault notes below. The original lock (OPA Brand Lockup Standard, locked 2026-08-06) was later found in the Drive archive at `On Point Amenities/04_Marketing/Content/_Archive/opa-marketing-machine_STALE_COPY_2026-08-11/my-brand/naming-and-tagline.md`, and section 5 was restored from it. Where this file and the enforced strings in `scripts/verify_brand.py` disagree, the verifier wins until Justin rules otherwise.
>
> **Authority:** Justin ruled on 2026-09-06 that this lock wins over whatever copy is live. Change the lock first, then the site, never the other way round.
>
> **Sources:** vault notes `2026.09.13_MKT_The_Archived_Naming_Lock_Wins_Over_Live_Site_Copy`, `2026.09.13_MKT_The_Brand_Lock_Is_An_Input_To_SEO_Work`, `2026.09.06_MKT_Website_Naming_Lock_Drift_and_Real_Deploy_Source`, and `scripts/verify_brand.py`.

This file is internal. It is listed in `.vercelignore` and is not served on opamenities.com.

---

## 1. Name

| Use | Exact string |
|---|---|
| Legal / full name | **On Point Amenities** |
| Short form (after the first reference) | **On Point** |
| Wordmark markup (header and footer, every templated page) | `<span class="wm">On Point<small>Amenities</small></span>` |
| Instagram handle (URL only, never shown as the name) | `instagram.com/onpointamenities` |

**First-reference rule:** the first mention on any page, including `<title>`, uses the full name **On Point Amenities**. SEO title rewrites must keep the brand name in the title.

## 2. Tagline

**Stocked right, managed tight. That's On Point.**

- This is the only footer tagline. In HTML the apostrophe is `&rsquo;`: `Stocked right, managed tight. That&rsquo;s On Point.`

## 3. Hero headline (homepage H1)

**Modern Convenience, Managed End-to-End.**

- Markup: `<h1>Modern Convenience, <span class="hl">Managed End-to-End.</span></h1>`

## 4. Call to action (one offer, one noun)

**Request Your Free On-Site Assessment**

- The offer is always an **assessment**, never a "consultation".

## 5. Demoted lines (body copy only, never a headline or tagline)

These three lines come from the original lock. They can go in paragraphs or campaign copy. Never put one under the logo, and never lead a page with one.

- "Convenience your people can count on."
- "The best amenity is the one your people never have to think about."
- "Vending that gives back instead of taking."

## 6. Locked homepage strings

- `<title>`: `On Point Amenities — Fully Managed Micro Markets, Smart Coolers & Modern Vending | South Denver Metro`
- `og:title`: `On Point Amenities — Modern Convenience, Managed End-to-End`
- Meta description: `On Point Amenities delivers fully managed micro markets, smart coolers, and modern cashless vending for South Denver Metro properties — installed, stocked, and serviced end-to-end at zero upfront cost. Veteran-owned. Request your free on-site assessment.`
- Sub-headline: `Fully managed micro markets, smart coolers, and modern vending for South Denver Metro's premium properties — so your team never has to think about it.`

## 7. Never

| Banned | Why |
|---|---|
| `OnPoint`, `OnPoint Amenities`, "OnPoint amenities" | The name is never one word. That includes image `alt` text, JSON-LD and meta tags. |
| "Smart Convenience, Always On Point." | An unlogged fourth tagline. Retired. |
| "Book a Free Consultation" | Retired CTA wording. |
| "Book a Free On-Site Consultation" | Retired CTA wording. |
| "Request My Free Consultation" | Retired CTA wording. |
| "consultation" (any case) | The offer is always an "assessment". |

## 8. Confirmed service claims (owner-confirmed 2026-09-23)

These wordings are safe to publish:

- $0 setup and upkeep
- monitored 24/7
- **next-day** service response
- same-day fixes when an order goes wrong
- restocked often, multiple times per week
- 100% cashless

Lead follow-up is a separate promise: "Justin follows up within 24 hours."

## 9. How this is enforced

- `scripts/verify_brand.py` runs in CI on every PR and every push to `master`. It checks the banned strings sitewide, the locked homepage strings, and the wordmark, CTA and tagline chrome on every templated page.
- If you add a locked string here, add it to the verifier in the same PR. A rule that isn't in the verifier will drift.
- Hand this file to any SEO or content session **before** it starts.
