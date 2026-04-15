"use client";

import { useEffect, useState, useCallback, use } from "react";

interface EventInfo {
  uid: string;
  name: string;
  description: string | null;
  date: string | null;
  location: string | null;
}

interface PhotoItem {
  id: string;
  session_id: string;
  seq: number;
  width: number;
  height: number;
  url: string;
  thumb_url: string;
  created_at: string | null;
}

export default function EventPage({
  params,
}: {
  params: Promise<{ uid: string }>;
}) {
  const { uid } = use(params);
  const [event, setEvent] = useState<EventInfo | null>(null);
  const [photos, setPhotos] = useState<PhotoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lightbox, setLightbox] = useState<PhotoItem | null>(null);

  useEffect(() => {
    if (!uid) return;

    async function fetchEvent() {
      try {
        const res = await fetch(`/api/api/public/events/${uid}`);
        if (res.status === 404) throw new Error("Event niet gevonden");
        if (res.status === 410) throw new Error("Dit event is afgelopen");
        if (!res.ok) throw new Error("Laden mislukt");
        const eventData = await res.json();
        setEvent(eventData);

        // Fetch photos
        const photosRes = await fetch(`/api/api/public/events/${uid}/photos`);
        if (photosRes.ok) {
          setPhotos(await photosRes.json());
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error");
      } finally {
        setLoading(false);
      }
    }

    fetchEvent();
  }, [uid]);

  // Auto-refresh photos every 15 seconds
  useEffect(() => {
    if (!uid || error || !event) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/api/public/events/${uid}/photos`);
        if (res.ok) setPhotos(await res.json());
      } catch {}
    }, 15_000);
    return () => clearInterval(interval);
  }, [uid, error, event]);

  const closeLightbox = useCallback(() => setLightbox(null), []);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeLightbox();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [closeLightbox]);

  if (loading) {
    return (
      <main style={{
        minHeight: "100dvh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #0f0f23, #1a1a2e)",
      }}>
        <div style={{
          width: 32,
          height: 32,
          border: "3px solid rgba(139, 92, 246, 0.2)",
          borderTopColor: "#8b5cf6",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </main>
    );
  }

  if (error || !event) {
    return (
      <main style={{
        minHeight: "100dvh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "2rem",
        background: "linear-gradient(135deg, #0f0f23, #1a1a2e)",
        color: "white",
      }}>
        <div>
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>😔</div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.5rem" }}>{error || "Event niet gevonden"}</h1>
          <p style={{ color: "#999" }}>Controleer of je de juiste QR-code hebt gescand.</p>
        </div>
      </main>
    );
  }

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("nl-NL", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  };

  return (
    <>
      <main style={{
        minHeight: "100dvh",
        maxWidth: 960,
        margin: "0 auto",
        padding: "0 1rem 3rem",
        color: "white",
      }}>
        {/* Header */}
        <header style={{
          textAlign: "center",
          padding: "3rem 1rem 2rem",
        }}>
          <div style={{ fontSize: "3rem", marginBottom: "0.75rem" }}>📸</div>
          <h1 style={{
            fontSize: "2rem",
            fontWeight: 800,
            background: "linear-gradient(135deg, #8b5cf6, #d946ef)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            marginBottom: "0.5rem",
          }}>
            {event.name}
          </h1>
          {event.description && (
            <p style={{
              fontSize: "1rem",
              color: "#999",
              maxWidth: 500,
              margin: "0 auto 1rem",
              lineHeight: 1.5,
            }}>
              {event.description}
            </p>
          )}
          <div style={{
            display: "flex",
            gap: "1.5rem",
            justifyContent: "center",
            flexWrap: "wrap",
          }}>
            {event.date && (
              <span style={{ fontSize: "0.85rem", color: "#999" }}>📅 {formatDate(event.date)}</span>
            )}
            {event.location && (
              <span style={{ fontSize: "0.85rem", color: "#999" }}>📍 {event.location}</span>
            )}
          </div>
          {photos.length > 0 && (
            <p style={{
              marginTop: "1rem",
              fontSize: "0.85rem",
              color: "#999",
            }}>
              {photos.length} foto{photos.length !== 1 ? "'s" : ""}
            </p>
          )}
        </header>

        {/* Gallery */}
        <section style={{ marginTop: "1rem" }}>
          {photos.length === 0 ? (
            <div style={{
              textAlign: "center",
              padding: "4rem 1rem",
              background: "rgba(255,255,255,0.03)",
              border: "1px dashed rgba(255,255,255,0.1)",
              borderRadius: 16,
            }}>
              <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>🎉</div>
              <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.5rem" }}>
                Welkom bij het event!
              </h2>
              <p style={{ color: "#999", fontSize: "0.9rem" }}>
                Foto&apos;s verschijnen hier zodra ze worden gemaakt.
              </p>
            </div>
          ) : (
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: "0.75rem",
            }}>
              {photos.map((photo) => (
                <div
                  key={photo.id}
                  style={{
                    aspectRatio: "7/5",
                    borderRadius: 12,
                    overflow: "hidden",
                    cursor: "pointer",
                    border: "1px solid rgba(255,255,255,0.06)",
                    background: "rgba(255,255,255,0.03)",
                    transition: "transform 0.2s, border-color 0.2s",
                  }}
                  onClick={() => setLightbox(photo)}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/api${photo.url}`}
                    alt={`Foto ${photo.seq}`}
                    loading="lazy"
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                    }}
                  />
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      {/* Lightbox */}
      {lightbox && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            background: "rgba(0,0,0,0.92)",
            backdropFilter: "blur(20px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          onClick={closeLightbox}
        >
          <button
            onClick={closeLightbox}
            style={{
              position: "absolute",
              top: "1rem",
              right: "1rem",
              background: "rgba(255,255,255,0.1)",
              border: "none",
              color: "white",
              width: 40,
              height: 40,
              borderRadius: "50%",
              fontSize: "1.2rem",
              cursor: "pointer",
              zIndex: 101,
            }}
            aria-label="Sluiten"
          >
            ✕
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`/api${lightbox.url}`}
            alt={`Foto ${lightbox.seq}`}
            style={{
              maxWidth: "90vw",
              maxHeight: "80vh",
              borderRadius: 16,
              objectFit: "contain",
            }}
            onClick={(e) => e.stopPropagation()}
          />
          <a
            href={`/api${lightbox.url}`}
            download={`photo_${lightbox.seq}.jpg`}
            style={{
              position: "absolute",
              bottom: "2rem",
              zIndex: 101,
              background: "#8b5cf6",
              color: "white",
              padding: "0.75rem 1.5rem",
              borderRadius: 12,
              textDecoration: "none",
              fontWeight: 600,
              fontSize: "0.9rem",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            ⬇ Download
          </a>
        </div>
      )}
    </>
  );
}
