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
  const url = `${API_URL}/${path}`;

  const headers: Record<string, string> = {
    "Content-Type": request.headers.get("Content-Type") || "application/json",
  };

  // Forward auth header
  const auth = request.headers.get("Authorization");
  if (auth) {
    headers["Authorization"] = auth;
  }

  try {
    const body =
      request.method !== "GET" && request.method !== "HEAD"
        ? await request.text()
        : undefined;

    const res = await fetch(url, {
      method: request.method,
      headers,
      body,
    });

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
