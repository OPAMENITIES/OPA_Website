// Edge Middleware: markdown content negotiation (acceptmarkdown.com).
// Requests with `Accept: text/markdown` on core pages get the markdown
// variant from /md/*.md; all other requests pass through to static HTML.
// Runs before the filesystem, which vercel.json rewrites cannot do.
export const config = {
  matcher: [
    '/',
    '/about', '/about/',
    '/services', '/services/',
    '/businesses', '/businesses/',
    '/contact', '/contact/',
    '/service-area', '/service-area/',
    '/blog', '/blog/',
    '/privacy', '/privacy/',
  ],
};

const MD = {
  '/': 'index',
  '/about': 'about',
  '/services': 'services',
  '/businesses': 'businesses',
  '/contact': 'contact',
  '/service-area': 'service-area',
  '/blog': 'blog',
  '/privacy': 'privacy',
};

export default async function middleware(request) {
  try {
    const accept = request.headers.get('accept') || '';
    if (!accept.includes('text/markdown')) return; // continue to static HTML
    const url = new URL(request.url);
    const key = url.pathname !== '/' ? url.pathname.replace(/\/+$/, '') : '/';
    const name = MD[key];
    if (!name) return;
    const res = await fetch(new URL('/md/' + name + '.md', url.origin));
    if (!res.ok) return;
    const body = await res.text();
    return new Response(body, {
      status: 200,
      headers: {
        'content-type': 'text/markdown; charset=utf-8',
        'vary': 'Accept',
        'x-robots-tag': 'noindex',
        'cache-control': 'public, max-age=0, must-revalidate',
      },
    });
  } catch {
    return; // never block the page on a middleware failure
  }
}
