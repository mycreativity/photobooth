"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { authFetch, clearTokens, isLoggedIn } from "@/lib/auth";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Event {
  id: string;
  uid: string;
  name: string;
  description: string | null;
  date: string | null;
  location: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
  photo_count?: number;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("nl-NL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

const PUBLIC_BASE = "https://booth.mycreativity.nl/e";

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function EventsPage() {
  const router = useRouter();
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: "",
    description: "",
    date: "",
    location: "",
  });
  const [creating, setCreating] = useState(false);

  // Edit modal
  const [editEvent, setEditEvent] = useState<Event | null>(null);
  const [editForm, setEditForm] = useState({
    name: "",
    description: "",
    date: "",
    location: "",
    is_active: true,
  });
  const [saving, setSaving] = useState(false);

  // QR modal
  const [qrEvent, setQrEvent] = useState<Event | null>(null);

  // Delete confirm
  const [deleteEvent, setDeleteEvent] = useState<Event | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Toast
  const [toast, setToast] = useState("");

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2500);
  }, []);

  /* ---- Fetch ---- */
  const fetchEvents = useCallback(async () => {
    try {
      const res = await authFetch("/api/api/events");
      if (res.status === 401) {
        clearTokens();
        router.replace("/login");
        return;
      }
      if (!res.ok) throw new Error("Failed to fetch events");
      setEvents(await res.json());
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
    fetchEvents();
  }, [router, fetchEvents]);

  /* ---- Create ---- */
  async function handleCreate() {
    setCreating(true);
    try {
      const body: Record<string, unknown> = { name: createForm.name };
      if (createForm.description) body.description = createForm.description;
      if (createForm.date) body.date = new Date(createForm.date).toISOString();
      if (createForm.location) body.location = createForm.location;

      const res = await authFetch("/api/api/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to create event");
      }
      setShowCreate(false);
      setCreateForm({ name: "", description: "", date: "", location: "" });
      showToast("Event aangemaakt");
      await fetchEvents();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    } finally {
      setCreating(false);
    }
  }

  /* ---- Edit ---- */
  function openEdit(ev: Event) {
    setEditEvent(ev);
    setEditForm({
      name: ev.name,
      description: ev.description || "",
      date: ev.date ? ev.date.slice(0, 16) : "",
      location: ev.location || "",
      is_active: ev.is_active,
    });
  }

  async function handleEdit() {
    if (!editEvent) return;
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        name: editForm.name,
        description: editForm.description || null,
        location: editForm.location || null,
        is_active: editForm.is_active,
      };
      if (editForm.date) body.date = new Date(editForm.date).toISOString();

      const res = await authFetch(`/api/api/events/${editEvent.uid}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Failed to update event");
      setEditEvent(null);
      showToast("Event bijgewerkt");
      await fetchEvents();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  }

  /* ---- Delete ---- */
  async function handleDelete() {
    if (!deleteEvent) return;
    setDeleting(true);
    try {
      const res = await authFetch(`/api/api/events/${deleteEvent.uid}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete event");
      setDeleteEvent(null);
      showToast("Event verwijderd");
      await fetchEvents();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    } finally {
      setDeleting(false);
    }
  }

  /* ---- Copy UID ---- */
  function copyUid(uid: string) {
    navigator.clipboard.writeText(uid);
    showToast(`UID "${uid}" gekopieerd`);
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
                className="px-3 py-1.5 text-sm text-gray-400 hover:text-white rounded-lg hover:bg-gray-800/50 transition"
              >
                Booths
              </a>
              <a
                href="/events"
                className="px-3 py-1.5 text-sm text-white bg-gray-800/70 rounded-lg font-medium"
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
            <h2 className="text-2xl font-bold text-white">Events</h2>
            <p className="text-gray-400 text-sm mt-1">
              {events.length} event{events.length !== 1 ? "s" : ""} aangemaakt
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-xl transition-all duration-200 flex items-center gap-2"
          >
            <span className="text-lg leading-none">+</span>
            Nieuw Event
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-8 h-8 border-4 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="text-center py-20">
            <p className="text-red-400">{error}</p>
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-20">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gray-800/50 mb-4">
              <span className="text-4xl">🎉</span>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Geen events</h3>
            <p className="text-gray-400 text-sm max-w-sm mx-auto">
              Maak een nieuw event aan om foto&apos;s te groeperen en een QR-code te
              genereren.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {events.map((ev) => (
              <div
                key={ev.id}
                className="group bg-gray-800/30 hover:bg-gray-800/50 border border-gray-700/30 hover:border-gray-600/50 rounded-2xl p-5 transition-all duration-200"
              >
                <div className="flex items-start justify-between">
                  {/* Left: info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="text-lg font-semibold text-white truncate">
                        {ev.name}
                      </h3>
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                          ev.is_active
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-gray-700/50 text-gray-400 border border-gray-600/30"
                        }`}
                      >
                        {ev.is_active ? "Actief" : "Inactief"}
                      </span>
                    </div>

                    <div className="flex items-center gap-4 text-sm text-gray-400 mb-2">
                      <button
                        onClick={() => copyUid(ev.uid)}
                        className="font-mono text-xs bg-gray-700/50 hover:bg-gray-700 px-2 py-0.5 rounded cursor-pointer transition flex items-center gap-1"
                        title="Kopieer UID"
                      >
                        {ev.uid}
                        <svg className="w-3 h-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      </button>
                      {ev.date && (
                        <span className="flex items-center gap-1">
                          📅 {formatDate(ev.date)}
                        </span>
                      )}
                      {ev.location && (
                        <span className="flex items-center gap-1">
                          📍 {ev.location}
                        </span>
                      )}
                    </div>

                    {ev.description && (
                      <p className="text-sm text-gray-500 truncate max-w-lg">
                        {ev.description}
                      </p>
                    )}
                    {(ev.photo_count ?? 0) > 0 && (
                      <a
                        href={`/events/${ev.uid}/photos`}
                        className="inline-flex items-center gap-1 mt-2 text-xs text-violet-400 hover:text-violet-300 transition"
                      >
                        📷 {ev.photo_count} foto{ev.photo_count !== 1 ? "'s" : ""} bekijken →
                      </a>
                    )}
                  </div>

                  {/* Right: actions */}
                  <div className="flex items-center gap-2 ml-4 shrink-0">
                    <button
                      onClick={() => setQrEvent(ev)}
                      className="p-2 text-gray-400 hover:text-white hover:bg-gray-700/50 rounded-lg transition"
                      title="QR-code"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3h7v7H3V3zm11 0h7v7h-7V3zM3 14h7v7H3v-7zm14 3h.01M17 17h.01M14 14h3v3h-3v-3zm3 3h3v3h-3v-3z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => openEdit(ev)}
                      className="p-2 text-gray-400 hover:text-white hover:bg-gray-700/50 rounded-lg transition"
                      title="Bewerken"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => setDeleteEvent(ev)}
                      className="p-2 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition"
                      title="Verwijderen"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* ---- Create Modal ---- */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700/50 rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-lg font-semibold text-white mb-4">Nieuw Event</h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-gray-400 block mb-1">Naam *</label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition"
                  placeholder="bv. Bruiloft Jan & Lisa"
                  autoFocus
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-1">Beschrijving</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition resize-none"
                  rows={2}
                  placeholder="Optionele beschrijving..."
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm text-gray-400 block mb-1">Datum</label>
                  <input
                    type="datetime-local"
                    value={createForm.date}
                    onChange={(e) => setCreateForm({ ...createForm, date: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition"
                  />
                </div>
                <div>
                  <label className="text-sm text-gray-400 block mb-1">Locatie</label>
                  <input
                    type="text"
                    value={createForm.location}
                    onChange={(e) => setCreateForm({ ...createForm, location: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition"
                    placeholder="bv. Amsterdam"
                  />
                </div>
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
                onClick={handleCreate}
                disabled={!createForm.name.trim() || creating}
                className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 rounded-xl transition"
              >
                {creating ? "Aanmaken..." : "Aanmaken"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Edit Modal ---- */}
      {editEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700/50 rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-lg font-semibold text-white mb-4">
              Event Bewerken
            </h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-gray-400 block mb-1">Naam *</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition"
                  autoFocus
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-1">Beschrijving</label>
                <textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition resize-none"
                  rows={2}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm text-gray-400 block mb-1">Datum</label>
                  <input
                    type="datetime-local"
                    value={editForm.date}
                    onChange={(e) => setEditForm({ ...editForm, date: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition"
                  />
                </div>
                <div>
                  <label className="text-sm text-gray-400 block mb-1">Locatie</label>
                  <input
                    type="text"
                    value={editForm.location}
                    onChange={(e) => setEditForm({ ...editForm, location: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition"
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editForm.is_active}
                    onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-violet-600"></div>
                </label>
                <span className="text-sm text-gray-400">Actief</span>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setEditEvent(null)}
                className="px-4 py-2 text-sm text-gray-400 hover:text-white transition"
              >
                Annuleren
              </button>
              <button
                onClick={handleEdit}
                disabled={!editForm.name.trim() || saving}
                className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 rounded-xl transition"
              >
                {saving ? "Opslaan..." : "Opslaan"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- QR Modal ---- */}
      {qrEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700/50 rounded-2xl p-6 w-full max-w-sm shadow-2xl text-center">
            <h3 className="text-lg font-semibold text-white mb-2">
              {qrEvent.name}
            </h3>
            <p className="text-sm text-gray-400 mb-6">
              Scan voor de publieke galerij
            </p>
            <div className="inline-flex p-4 bg-white rounded-2xl mb-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(`${PUBLIC_BASE}/${qrEvent.uid}`)}`}
                alt={`QR code voor ${qrEvent.name}`}
                width={200}
                height={200}
              />
            </div>
            <p className="text-xs text-gray-500 font-mono mb-1">
              {PUBLIC_BASE}/{qrEvent.uid}
            </p>
            <p className="text-xs text-gray-600 mb-6">
              UID: {qrEvent.uid}
            </p>
            <div className="flex justify-center gap-3">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(`${PUBLIC_BASE}/${qrEvent.uid}`);
                  showToast("URL gekopieerd");
                }}
                className="px-4 py-2 text-sm text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-xl transition"
              >
                Kopieer URL
              </button>
              <button
                onClick={() => setQrEvent(null)}
                className="px-4 py-2 text-sm text-gray-400 hover:text-white transition"
              >
                Sluiten
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Delete Confirmation ---- */}
      {deleteEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700/50 rounded-2xl p-6 w-full max-w-sm shadow-2xl">
            <h3 className="text-lg font-semibold text-white mb-2">
              Event Verwijderen
            </h3>
            <p className="text-sm text-gray-400 mb-6">
              Weet je zeker dat je <strong className="text-white">{deleteEvent.name}</strong> wilt
              verwijderen? Dit kan niet ongedaan worden.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteEvent(null)}
                className="px-4 py-2 text-sm text-gray-400 hover:text-white transition"
              >
                Annuleren
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-xl transition"
              >
                {deleting ? "Verwijderen..." : "Verwijderen"}
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
