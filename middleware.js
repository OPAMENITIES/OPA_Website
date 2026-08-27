// Edge Middleware — agentic behaviors for the static mirror.
//
// 1. Markdown content negotiation (acceptmarkdown.com): requests with
//    `Accept: text/markdown` on core pages get the /md/*.md variant.
// 2. Agent-friendly 404: nonexistent paths return a DIRECT 404 with a short
//    markdown recovery body for non-browser clients (curl, agents sending
//    Accept: */*), instead of the 308 trailing-slash redirect. Browsers
//    (Accept: text/html) keep today's behavior: redirect → branded 404.html.
//
// VALID is generated from the repo tree (every dir containing index.html).
// If a page is ever added to the mirror, add its path here — or it will 404
// for agents. The rebuild replaces this with build-time generation.
export const config = {
  matcher: ['/((?!api/|md/|wp-content/|wp-includes/|_vercel|.*\\..*).*)'],
};

const VALID = new Set([
  '/', '/about/', '/blog/', '/businesses/', '/contact/', '/privacy/',
  '/service-area/', '/services/', '/businesses/multifamily/', '/businesses/dealerships/', '/businesses/gyms/', '/businesses/offices/', '/businesses/hospitality/', '/businesses/healthcare/',
  '/apartment-community-amenities-in-denver-how-modern-convenience-boosts-property-appeal/',
  '/cashless-smart-coolers-secure-refreshments-for-public-spaces/',
  '/hospital-vending-services-in-denver-24-7-refreshments-for-healthcare-facilities/',
  '/hospitality-vending-in-south-denver-24-7-refreshments-made-easy/',
  '/meet-on-point-amenities-modern-vending-and-amenity-solutions-for-workplaces-and-properties/',
  '/modern-smart-stores-and-smart-coolers-for-gyms-and-fitness-centers/',
  '/office-micro-markets-in-denver-transforming-workplace-breakrooms/',
  '/vending-services-south-denver-modern-solutions-multifamily-properties/',
  '/category/breakroom-solutions/', '/category/refreshment-solutions/',
  '/category/smart-coolers/', '/category/uncategorized/', '/category/vending-services/',
  '/tag/ai-powered-smart-coolers/', '/tag/apartment-vending/', '/tag/cashless-technology/',
  '/tag/cashless-vending/', '/tag/gym-amenities/', '/tag/healthcare-amenities/',
  '/tag/healthy-vending/', '/tag/hospital-vending/', '/tag/hospitality-vending/',
  '/tag/hotel-amenities/', '/tag/hotel-vending/', '/tag/micro-markets/',
  '/tag/modern-vending/', '/tag/secure-self-service-food-solutions/',
  '/tag/self-serve-markets/', '/tag/smart-cooler-technology/',
  '/tag/smart-coolers-for-healthcare-facilities/', '/tag/smart-coolers-for-healthcare/',
  '/tag/smart-coolers/', '/tag/smart-stores/', '/tag/unattended-retail-coolers/',
  '/tag/vending-machines/', '/tag/vending-services/', '/tag/vending-technology/',
  '/tag/workplace-refreshments/',
]);

const MD = {
  '/': 'index',
  '/about/': 'about',
  '/services/': 'services',
  '/businesses/': 'businesses',
  '/contact/': 'contact',
  '/service-area/': 'service-area',
  '/blog/': 'blog',
  '/privacy/': 'privacy',
  '/businesses/multifamily/': 'businesses-multifamily',
  '/businesses/dealerships/': 'businesses-dealerships',
  '/businesses/gyms/': 'businesses-gyms',
  '/businesses/offices/': 'businesses-offices',
  '/businesses/hospitality/': 'businesses-hospitality',
  '/businesses/healthcare/': 'businesses-healthcare',
};

const NOT_FOUND_MD = `# 404 — Page not found

This path does not exist on opamenities.com. Where to look next:

- Sitemap: https://opamenities.com/sitemap.xml
- Agent guide: https://opamenities.com/llms.txt
- [Home](https://opamenities.com/) · [Services](https://opamenities.com/services/) · [Businesses We Serve](https://opamenities.com/businesses/) · [Where We Serve](https://opamenities.com/service-area/) · [About](https://opamenities.com/about/) · [Blog](https://opamenities.com/blog/) · [Contact](https://opamenities.com/contact/)

On Point Amenities — smart vending & micro markets, South Denver Metro. Book a free on-site consultation: https://opamenities.com/contact/ · +1-720-828-2170 · info@opamenities.com
`;

export default async function middleware(request) {
  try {
    const accept = request.headers.get('accept') || '';
    const url = new URL(request.url);
    const key = url.pathname === '/' ? '/' : url.pathname.replace(/\/+$/, '') + '/';

    if (VALID.has(key)) {
      // Markdown content negotiation on core pages.
      if (accept.includes('text/markdown') && MD[key]) {
        const res = await fetch(new URL('/md/' + MD[key] + '.md', url.origin));
        if (!res.ok) return;
        return new Response(await res.text(), {
          status: 200,
          headers: {
            'content-type': 'text/markdown; charset=utf-8',
            'vary': 'Accept',
            'x-robots-tag': 'noindex',
            'cache-control': 'public, max-age=0, must-revalidate',
          },
        });
      }
      return; // real page, default handling
    }

    // Nonexistent path. Browsers keep the branded HTML 404 flow; everything
    // else (curl, agents) gets an immediate 404 with a markdown body.
    if (accept.includes('text/html') && !accept.includes('text/markdown')) return;
    return new Response(NOT_FOUND_MD, {
      status: 404,
      headers: {
        'content-type': 'text/markdown; charset=utf-8',
        'vary': 'Accept',
        'x-robots-tag': 'noindex',
      },
    });
  } catch {
    return; // never block a page on middleware failure
  }
}
