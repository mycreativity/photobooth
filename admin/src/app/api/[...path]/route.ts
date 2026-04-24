/**
 * Catch-all API proxy: forwards all /api/* requests to the FastAPI server.
 * This ensures all API calls are server-to-server (S2S) via Docker network.
 */
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

async function proxyRequest(
  request: NextRequest,
  params: { path: string[] }
) {
  const path = params.path.join("/");
  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${API_URL}/${path}${searchParams ? `?${searchParams}` : ""}`;

  const headers: Record<string, string> = {};

  // Forward content-type (but NOT for multipart — let fetch set the boundary)
  const contentType = request.headers.get("Content-Type") || "";
  if (contentType && !contentType.includes("multipart/form-data")) {
    headers["Content-Type"] = contentType;
  }

  // Forward auth header
  const auth = request.headers.get("Authorization");
  if (auth) {
    headers["Authorization"] = auth;
  }

  try {
    let body: BodyInit | undefined;
    if (request.method !== "GET" && request.method !== "HEAD") {
      // For multipart/form-data, pass the raw body as ArrayBuffer
      if (contentType.includes("multipart/form-data")) {
        body = await request.arrayBuffer();
        // Re-set content type WITH boundary for multipart
        headers["Content-Type"] = contentType;
      } else {
        body = await request.text();
      }
    }

    const res = await fetch(url, {
      method: request.method,
      headers,
      body,
    });

    // For image/binary responses, return as-is
    const resContentType = res.headers.get("Content-Type") || "";
    if (
      resContentType.startsWith("image/") ||
      resContentType.startsWith("application/octet-stream")
    ) {
      const data = await res.arrayBuffer();
      return new NextResponse(data, {
        status: res.status,
        headers: {
          "Content-Type": resContentType,
          "Cache-Control": "public, max-age=3600",
        },
      });
    }

    // JSON responses
    const data = await res.json().catch(() => null);
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error(`Proxy error: ${url}`, error);
    return NextResponse.json(
      { detail: "Server unreachable" },
      { status: 502 }
    );
  }
}
