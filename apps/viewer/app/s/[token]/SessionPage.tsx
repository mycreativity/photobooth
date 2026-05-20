"use client";

import { useEffect, useState, use } from "react";
import { SessionViewer } from "@/components/SessionViewer";
import { ErrorState } from "@/components/ErrorState";
import { Loader2 } from "lucide-react";
import styles from "./SessionPage.module.css";

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

export default function SessionPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const [session, setSession] = useState<SessionData | null>(null);
  const [photos, setPhotos] = useState<PhotoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ code: number; message: string } | null>(null);

  useEffect(() => {
    if (!token) return;

    async function fetchData() {
      try {
        const sessionRes = await fetch(`/api/api/public/sessions/${token}`);
        if (sessionRes.status === 404) {
          setError({ code: 404, message: "Sessie niet gevonden" });
          return;
        }
        if (sessionRes.status === 410) {
          setError({ code: 410, message: "Deze sessie is verlopen" });
          return;
        }
        if (!sessionRes.ok) {
          setError({ code: 500, message: "Er ging iets mis" });
          return;
        }
        const sessionData = await sessionRes.json();
        setSession(sessionData);

        const photosRes = await fetch(`/api/api/public/sessions/${token}/photos`);
        if (photosRes.ok) {
          setPhotos(await photosRes.json());
        }
      } catch {
        setError({ code: 500, message: "Kan geen verbinding maken" });
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [token]);

  if (loading) {
    return (
      <div className={styles.loaderWrap}>
        <Loader2 size={32} className={styles.spinner} />
      </div>
    );
  }

  if (error) {
    return <ErrorState code={error.code} message={error.message} />;
  }

  if (!session) {
    return <ErrorState code={404} message="Sessie niet gevonden" />;
  }

  return (
    <SessionViewer
      session={session}
      photos={photos}
    />
  );
}
