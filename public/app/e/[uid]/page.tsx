"use client";

import { useEffect, useState, useCallback } from "react";

interface EventInfo {
  uid: string;
  name: string;
  description: string | null;
  date: string | null;
  location: string | null;
}

export default function EventPage({
  params,
}: {
  params: Promise<{ uid: string }>;
}) {
  const [event, setEvent] = useState<EventInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uid, setUid] = useState("");
  const [lightbox, setLightbox] = useState<string | null>(null);

  useEffect(() => {
    params.then((p) => setUid(p.uid));
  }, [params]);

  useEffect(() => {
    if (!uid) return;
    fetchEvent();
  }, [uid]);

  async function fetchEvent() {
    try {
      const res = await fetch(`/api/api/public/events/${uid}`);
      if (res.status === 404) throw new Error("Event niet gevonden");
      if (res.status === 410) throw new Error("Dit event is afgelopen");
      if (!res.ok) throw new Error("Laden mislukt");
      setEvent(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

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
      <main className="loading-screen">
        <div className="spinner" />
        <style jsx>{`
          .loading-screen {
            min-height: 100dvh;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid rgba(139, 92, 246, 0.2);
            border-top-color: #8b5cf6;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
          }
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </main>
    );
  }

  if (error || !event) {
    return (
      <main className="error-screen">
        <div className="error-content">
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>😔</div>
          <h1>{error || "Event niet gevonden"}</h1>
          <p>Controleer of je de juiste QR-code hebt gescand.</p>
        </div>
        <style jsx>{`
          .error-screen {
            min-height: 100dvh;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 2rem;
          }
          .error-content h1 {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
          }
          .error-content p {
            color: var(--text-muted);
          }
        `}</style>
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
      <main className="event-page">
        {/* Header */}
        <header className="event-header">
          <div className="header-badge">📸</div>
          <h1 className="event-title">{event.name}</h1>
          {event.description && (
            <p className="event-description">{event.description}</p>
          )}
          <div className="event-meta">
            {event.date && (
              <span className="meta-item">📅 {formatDate(event.date)}</span>
            )}
            {event.location && (
              <span className="meta-item">📍 {event.location}</span>
            )}
          </div>
        </header>

        {/* Photo gallery placeholder */}
        <section className="gallery-section">
          <div className="gallery-empty">
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>🎉</div>
            <h2>Welkom bij het event!</h2>
            <p>Foto&apos;s verschijnen hier zodra ze worden gemaakt.</p>
          </div>
        </section>
      </main>

      {/* Lightbox */}
      {lightbox && (
        <div className="lightbox" onClick={closeLightbox}>
          <button
            className="lightbox-close"
            onClick={closeLightbox}
            aria-label="Sluiten"
          >
            ✕
          </button>
          <img src={lightbox} alt="Photo" />
          <a
            href={lightbox}
            download
            className="lightbox-download btn btn-primary"
            onClick={(e) => e.stopPropagation()}
          >
            ⬇ Download
          </a>
        </div>
      )}

      <style jsx>{`
        .event-page {
          min-height: 100dvh;
          max-width: 960px;
          margin: 0 auto;
          padding: 0 1rem 3rem;
        }

        .event-header {
          text-align: center;
          padding: 3rem 1rem 2rem;
        }

        .header-badge {
          font-size: 3rem;
          margin-bottom: 0.75rem;
        }

        .event-title {
          font-size: 2rem;
          font-weight: 800;
          background: linear-gradient(135deg, #8b5cf6, #d946ef);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          margin-bottom: 0.5rem;
        }

        .event-description {
          font-size: 1rem;
          color: var(--text-muted);
          max-width: 500px;
          margin: 0 auto 1rem;
          line-height: 1.5;
        }

        .event-meta {
          display: flex;
          gap: 1.5rem;
          justify-content: center;
          flex-wrap: wrap;
        }

        .meta-item {
          font-size: 0.85rem;
          color: var(--text-muted);
        }

        .gallery-section {
          margin-top: 2rem;
        }

        .gallery-empty {
          text-align: center;
          padding: 4rem 1rem;
          background: var(--bg-card);
          border: 1px dashed var(--border);
          border-radius: 16px;
        }

        .gallery-empty h2 {
          font-size: 1.25rem;
          font-weight: 600;
          margin-bottom: 0.5rem;
        }

        .gallery-empty p {
          color: var(--text-muted);
          font-size: 0.9rem;
        }

        .lightbox-close {
          position: absolute;
          top: 1rem;
          right: 1rem;
          background: rgba(255,255,255,0.1);
          border: none;
          color: white;
          width: 40px;
          height: 40px;
          border-radius: 50%;
          font-size: 1.2rem;
          cursor: pointer;
          z-index: 101;
        }

        .lightbox-download {
          position: absolute;
          bottom: 2rem;
          z-index: 101;
        }
      `}</style>
    </>
  );
}
