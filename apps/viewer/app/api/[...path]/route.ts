import { NextRequest, NextResponse } from "next/server";

/**
 * Catch-all API proxy route handler.
 *
 * Forwards all requests from /api/* to the internal API server.
 * Resolves API_URL at runtime (not build time), which is required
 * for Next.js standalone mode in Docker.
 *
 * The browser never sees the internal API URL or tokens.
 */

const API_URL = () => process.env.API_URL || "http://localhost:8000";

async function proxyRequest(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const targetPath = path.join("/");
  const url = new URL(request.url);
  const target = `${API_URL()}/${targetPath}${url.search}`;

  const headers = new Headers(request.headers);
  // Remove host header to avoid conflicts
  headers.delete("host");

  const init: RequestInit = {
    method: request.method,
    headers,
    // @ts-expect-error duplex is needed for streaming request bodies
    duplex: "half",
  };

  // Forward body for non-GET/HEAD requests
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
  }

  try {
    const response = await fetch(target, init);

    // Stream the response back
    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: {
        "content-type": response.headers.get("content-type") || "application/octet-stream",
        "content-length": response.headers.get("content-length") || "",
        "cache-control": response.headers.get("cache-control") || "no-cache",
      },
    });
  } catch (error) {
    console.error(`API proxy error: ${target}`, error);
    return NextResponse.json(
      { detail: "API unavailable" },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
export const PATCH = proxyRequest;
