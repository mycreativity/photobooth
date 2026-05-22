# Rule: API Proxy Architecture

## Never call the API directly from the browser

All API communication MUST be proxied through Next.js. This applies to every frontend app in the monorepo (viewer, admin).

### Requirements

1. **No direct API URLs in client code** — Never use `NEXT_PUBLIC_API_URL` or hardcode the API domain. The browser should only ever talk to the Next.js server.
2. **Next.js rewrites for data** — Use `rewrites()` in `next.config.ts` to proxy `/api/:path*` to the internal API.
3. **No tokens in the browser** — JWT tokens, API keys, and internal service URLs must never be exposed client-side. Use server-side data fetching or session cookies.
4. **Runtime env resolution** — Since Next.js standalone mode bakes `next.config.ts` at build time, use **Next.js middleware** or **route handlers** for proxying when the API URL is only known at runtime.

### Correct patterns

```tsx
// ✅ Client component — relative URL, proxied by Next.js
<img src="/api/public/photos/abc123" />

// ✅ Server component — direct internal call
const res = await fetch(`${process.env.API_URL}/api/public/sessions/${token}`);

// ✅ Next.js route handler as proxy
// app/api/[...path]/route.ts → forwards to internal API
```

### Forbidden patterns

```tsx
// ❌ Never expose API domain to the browser
<img src={`${process.env.NEXT_PUBLIC_API_URL}/api/photos/abc`} />

// ❌ Never use NEXT_PUBLIC_ for API URLs
NEXT_PUBLIC_API_URL=https://photobooth-api.mycreativity.nl

// ❌ Never send JWTs from client to API directly
fetch("https://api.example.com", { headers: { Authorization: `Bearer ${token}` } });
```
