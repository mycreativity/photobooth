import type { Metadata } from "next";

interface SessionData {
  token: string;
  layout: string | null;
  photo_count: number;
  created_at: string | null;
  event: {
    name: string;
    description: string | null;
    date: string | null;
    location: string | null;
  } | null;
}

async function getSession(token: string): Promise<SessionData | null> {
  const apiUrl = process.env.API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/public/sessions/${token}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  const session = await getSession(token);
  const eventName = session?.event?.name ?? "Photobooth";

  return {
    title: `${eventName} — LOOMO Photobooth`,
    description: `Bekijk en deel je photobooth foto's van ${eventName}`,
    openGraph: {
      title: eventName,
      description: `Bekijk en deel je photobooth foto's`,
      type: "website",
    },
  };
}

export { default } from "./SessionPage";
