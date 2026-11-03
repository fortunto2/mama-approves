// bro.rustman.org → static BroCheck on Pages. The DNS record still points at the old laptop
// tunnel; a route runs before the origin, so this serves the site without touching DNS.
export default {
  async fetch(req) {
    const u = new URL(req.url);
    u.hostname = 'brocheck.pages.dev';
    return fetch(new Request(u, req));
  },
};
