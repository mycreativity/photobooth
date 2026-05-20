import type { Metadata } from "next";
import { SessionViewer } from "@/components/SessionViewer";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";

const API = process.env.API_URL || "http://localhost:8000";

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

interface PhotoItem {
  id: string;
  seq: number;
  variant: string;
  width: number;
  height: number;
  url: string;
  created_at: string | null;
}

async function getSession(token: string): Promise<{ data: SessionData | null; status: number }> {
  try {
    const res = await fetch(`${API}/api/public/sessions/${token}`, {
      cache: "no-store",
    });
    if (!res.ok) return { data: null, status: res.status };
    return { data: await res.json(), status: 200 };
  } catch {
    return { data: null, status: 500 };
  }
}

async function getPhotos(token: string): Promise<PhotoItem[]> {
  try {
    const res = await fetch(`${API}/api/public/sessions/${token}/photos`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  const { data: session } = await getSession(token);
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

export default async function SessionPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const [{ data: session, status }, photos] = await Promise.all([
    getSession(token),
    getPhotos(token),
  ]);

  if (!session) {
    const message =
      status === 410
        ? "Deze sessie is verlopen"
        : status === 404
          ? "Sessie niet gevonden"
          : "Er ging iets mis";
    return <ErrorState code={status} message={message} />;
  }

  if (photos.length === 0) {
    return <EmptyState eventName={session.event?.name} />;
  }

  return <SessionViewer session={session} photos={photos} />;
}
