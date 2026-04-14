"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { authFetch, clearTokens, isLoggedIn } from "@/lib/auth";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Booth {
  id: string;
  booth_id: string;
  name: string | null;
  event_id: string | null;
  status: string;
  last_seen: string | null;
  cpu_percent: number | null;
  camera_connected: boolean;
  uptime_seconds: number | null;
  version: string | null;
}

interface EventOption {
  id: string;
  uid: string;
  name: string;
  is_active: boolean;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatUptime(seconds: number | null): string {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}u ${m}m` : `${m}m`;
}

function formatLastSeen(iso: string | null): string {
  if (!iso) return "Nooit";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  if (diff < 60_000) return "Nu";
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m geleden`;
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}u geleden`;
  return d.toLocaleDateString("nl-NL");
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function DashboardPage() {
  const router = useRouter();
  const [booths, setBooths] = useState<Booth[]>([]);
  const [events, setEvents] = useState<EventOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Create booth modal
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ booth_id: "", name: "" });
  const [creating, setCreating] = useState(false);

  // API key display modal (after creation or regeneration)
  const [apiKeyInfo, setApiKeyInfo] = useState<{
    booth_id: string;
    api_key: string;
  } | null>(null);

  // Toast
  const [toast, setToast] = useState("");
  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2500);
  }, []);

  /* ---- Fetch ---- */
  const fetchData = useCallback(async () => {
    try {
      const [boothRes, eventRes] = await Promise.all([
        authFetch("/api/api/booths"),
        authFetch("/api/api/events"),
      ]);

      if (boothRes.status === 401) {
        clearTokens();
        router.replace("/login");
        return;
      }

      if (!boothRes.ok) throw new Error("Failed to fetch booths");
      if (!eventRes.ok) throw new Error("Failed to fetch events");

      setBooths(await boothRes.json());
      setEvents(await eventRes.json());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    fetchData();
    const interval = setInterval(fetchData, 10_000);
    return () => clearInterval(interval);
  }, [router, fetchData]);

  /* ---- Create Booth ---- */
  async function handleCreateBooth() {
    setCreating(true);
    try {
      const res = await authFetch("/api/api/booths", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          booth_id: createForm.booth_id.trim(),
          name: createForm.name.trim() || null,
        }),
      });

      if (res.status === 409) {
        showToast("Booth ID bestaat al");
        return;
      }
      if (!res.ok) throw new Error("Failed to create booth");

      const data = await res.json();
      setShowCreate(false);
      setCreateForm({ booth_id: "", name: "" });
      setApiKeyInfo({ booth_id: data.booth_id, api_key: data.api_key });
      await fetchData();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    } finally {
      setCreating(false);
    }
  }

  /* ---- Regenerate Key ---- */
  async function handleRegenerateKey(boothId: string) {
    if (!confirm(`Nieuwe API key genereren voor ${boothId}? De oude key wordt ongeldig.`))
      return;
    try {
      const res = await authFetch(`/api/api/booths/${boothId}/regenerate-key`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Failed to regenerate key");
      const data = await res.json();
      setApiKeyInfo({ booth_id: data.booth_id, api_key: data.api_key });
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    }
  }

  /* ---- Update Event Coupling ---- */
  async function handleEventChange(boothId: string, eventId: string) {
    try {
      const res = await authFetch(`/api/api/booths/${boothId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: eventId || null }),
      });
      if (!res.ok) throw new Error("Failed to update booth");
      showToast("Event gekoppeld");
      await fetchData();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    }
  }

  /* ---- Delete Booth ---- */
  async function handleDeleteBooth(boothId: string) {
    if (!confirm(`Booth "${boothId}" verwijderen?`)) return;
    try {
      const res = await authFetch(`/api/api/booths/${boothId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete booth");
      showToast("Booth verwijderd");
      await fetchData();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    }
  }

  function getEventName(eventId: string | null): string {
    if (!eventId) return "";
    const ev = events.find((e) => e.id === eventId);
    return ev ? ev.name : "";
  }

  /* ---- Render ---- */
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800/50 bg-gray-900/50 backdrop-blur-xl sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📸</span>
            <h1 className="text-xl font-bold text-white">Photobooth Admin</h1>
          </div>
          <div className="flex items-center gap-6">
            <nav className="flex items-center gap-1">
              <a
                href="/"
                className="px-3 py-1.5 text-sm text-white bg-gray-800/70 rounded-lg font-medium"
              >
                Booths
              </a>
              <a
                href="/events"
                className="px-3 py-1.5 text-sm text-gray-400 hover:text-white rounded-lg hover:bg-gray-800/50 transition"
              >
                Events
              </a>
            </nav>
            <button
              onClick={() => {
                clearTokens();
                router.replace("/login");
              }}
              className="text-gray-400 hover:text-white text-sm transition"
            >
              Uitloggen
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-white">Booths</h2>
            <p className="text-gray-400 text-sm mt-1">
              {booths.length} booth{booths.length !== 1 ? "s" : ""} geregistreerd
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-sm text-gray-400">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Live
            </span>
            <button
              onClick={() => setShowCreate(true)}
              className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-xl transition-all duration-200 flex items-center gap-2"
            >
              <span className="text-lg leading-none">+</span>
              Nieuwe Booth
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-8 h-8 border-4 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="text-center py-20">
            <p className="text-red-400">{error}</p>
          </div>
        ) : booths.length === 0 ? (
          <div className="text-center py-20">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gray-800/50 mb-4">
              <span className="text-4xl">📷</span>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Geen booths</h3>
            <p className="text-gray-400 text-sm max-w-sm mx-auto">
              Registreer een nieuwe booth om te beginnen met beheren.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {booths.map((booth) => (
              <div
                key={booth.id}
                className="group bg-gray-800/30 hover:bg-gray-800/50 border border-gray-700/30 hover:border-gray-600/50 rounded-2xl p-5 transition-all duration-200"
              >
                {/* Status header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2.5 h-2.5 rounded-full ${
                        booth.status === "online"
                          ? "bg-emerald-500 shadow-lg shadow-emerald-500/50"
                          : "bg-gray-600"
                      }`}
                    />
                    <span className="text-sm font-medium text-gray-300">
                      {booth.status === "online" ? "Online" : "Offline"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    {booth.version && (
                      <span className="text-xs text-gray-500 bg-gray-700/50 px-2 py-0.5 rounded-full">
                        v{booth.version}
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRegenerateKey(booth.booth_id);
                      }}
                      className="p-1 text-gray-500 hover:text-amber-400 rounded transition opacity-0 group-hover:opacity-100"
                      title="Regenereer API key"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                      </svg>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteBooth(booth.booth_id);
                      }}
                      className="p-1 text-gray-500 hover:text-red-400 rounded transition opacity-0 group-hover:opacity-100"
                      title="Verwijder booth"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>

                {/* Name — clickable to detail */}
                <div
                  className="cursor-pointer"
                  onClick={() => router.push(`/booths/${booth.booth_id}`)}
                >
                  <h3 className="text-lg font-semibold text-white mb-1 group-hover:text-violet-300 transition">
                    {booth.name || booth.booth_id}
                  </h3>
                  <p className="text-xs text-gray-500 font-mono mb-4">{booth.booth_id}</p>
                </div>

                {/* Event coupling */}
                <div className="mb-4">
                  <label className="text-xs text-gray-500 block mb-1">Event</label>
                  <select
                    value={booth.event_id || ""}
                    onChange={(e) => handleEventChange(booth.booth_id, e.target.value)}
                    className="w-full bg-gray-800/70 border border-gray-700/50 rounded-lg px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-violet-500 transition appearance-none cursor-pointer"
                  >
                    <option value="">Geen event</option>
                    {events
                      .filter((ev) => ev.is_active)
                      .map((ev) => (
                        <option key={ev.id} value={ev.id}>
                          {ev.name}
                        </option>
                      ))}
                  </select>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <p className="text-xs text-gray-500 mb-0.5">CPU</p>
                    <p className="text-sm font-medium text-gray-300">
                      {booth.cpu_percent != null ? `${booth.cpu_percent}%` : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-0.5">Camera</p>
                    <p className="text-sm font-medium">
                      {booth.camera_connected ? (
                        <span className="text-emerald-400">✓</span>
                      ) : (
                        <span className="text-gray-500">✗</span>
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-0.5">Uptime</p>
                    <p className="text-sm font-medium text-gray-300">
                      {formatUptime(booth.uptime_seconds)}
                    </p>
                  </div>
                </div>

                {/* Last seen + event badge */}
                <div className="mt-4 pt-3 border-t border-gray-700/30 flex items-center justify-between">
                  <p className="text-xs text-gray-500">
                    Laatst gezien: {formatLastSeen(booth.last_seen)}
                  </p>
                  {booth.event_id && (
                    <span className="text-xs text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-full truncate max-w-[120px]">
                      {getEventName(booth.event_id)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* ---- Create Booth Modal ---- */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700/50 rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-lg font-semibold text-white mb-4">Nieuwe Booth</h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-gray-400 block mb-1">Booth ID *</label>
                <input
                  type="text"
                  value={createForm.booth_id}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, booth_id: e.target.value })
                  }
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-violet-500 transition"
                  placeholder="bv. booth-001"
                  autoFocus
                />
                <p className="text-xs text-gray-600 mt-1">
                  Unieke identifier — gebruik in booth.toml
                </p>
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-1">Naam</label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, name: e.target.value })
                  }
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition"
                  placeholder="bv. Photobooth Lobby"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-sm text-gray-400 hover:text-white transition"
              >
                Annuleren
              </button>
              <button
                onClick={handleCreateBooth}
                disabled={!createForm.booth_id.trim() || creating}
                className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 rounded-xl transition"
              >
                {creating ? "Aanmaken..." : "Registreren"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- API Key Display Modal ---- */}
      {apiKeyInfo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700/50 rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white">API Key</h3>
                <p className="text-xs text-gray-400">{apiKeyInfo.booth_id}</p>
              </div>
            </div>

            <div className="bg-gray-800 border border-amber-500/20 rounded-xl p-4 mb-4">
              <p className="text-xs text-amber-400 mb-2 font-medium">
                ⚠️ Deze key wordt maar één keer getoond!
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-sm text-white font-mono break-all bg-gray-900/50 p-2 rounded">
                  {apiKeyInfo.api_key}
                </code>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(apiKeyInfo.api_key);
                    showToast("API key gekopieerd");
                  }}
                  className="shrink-0 p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition"
                  title="Kopieer"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </button>
              </div>
            </div>

            <div className="bg-gray-800/50 rounded-xl p-3 mb-6">
              <p className="text-xs text-gray-400 mb-1">Configureer in booth.toml:</p>
              <code className="text-xs text-gray-300 font-mono">
                [server]<br />
                booth_id = &quot;{apiKeyInfo.booth_id}&quot;<br />
                api_key = &quot;{apiKeyInfo.api_key}&quot;
              </code>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setApiKeyInfo(null)}
                className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-xl transition"
              >
                Begrepen, sluiten
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Toast ---- */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-gray-800 border border-gray-700/50 text-white text-sm px-4 py-2.5 rounded-xl shadow-lg animate-[fadeIn_0.2s]">
          {toast}
        </div>
      )}
    </div>
  );
}
