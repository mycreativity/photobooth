"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { authFetch, clearTokens, isLoggedIn } from "@/lib/auth";
import PageHeader from "@/app/components/PageHeader";
import {
  Button, Badge, Card, Modal, Toast, EmptyState, Spinner, Input, Select,
} from "@/app/components/ui";
import {
  Plus, Key, Trash2, Copy, Camera, Cpu, Clock, Eye, Check, X as XIcon, AlertTriangle,
} from "lucide-react";

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

  // API key display modal
  const [apiKeyInfo, setApiKeyInfo] = useState<{
    booth_id: string;
    api_key: string;
  } | null>(null);

  // Toast
  const [toast, setToast] = useState("");
  const showToast = useCallback((msg: string) => {
    setToast(msg);
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
    <>
      <PageHeader
        title="Booths"
        subtitle={`${booths.length} booth${booths.length !== 1 ? "s" : ""} geregistreerd`}
        actions={
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              icon={<Plus />}
              onClick={() => setShowCreate(true)}
            >
              Nieuwe Booth
            </Button>
          </div>
        }
      />

        {loading ? (
          <div className="flex justify-center py-20">
            <Spinner size="lg" />
          </div>
        ) : error ? (
          <div className="text-center py-20">
            <p className="text-[var(--danger)]">{error}</p>
          </div>
        ) : booths.length === 0 ? (
          <EmptyState
            icon={<Camera />}
            title="Geen booths"
            description="Registreer een nieuwe booth om te beginnen met beheren."
            action={{ label: "Nieuwe Booth", onClick: () => setShowCreate(true) }}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {booths.map((booth) => (
              <Card key={booth.id} hover>
                {/* Status header */}
                <div className="flex items-center justify-between mb-4">
                  <Badge
                    variant={booth.status === "online" ? "success" : "neutral"}
                    dot
                  >
                    {booth.status === "online" ? "Online" : "Offline"}
                  </Badge>
                  <div className="flex items-center gap-1">
                    {booth.version && (
                      <span className="text-xs text-[var(--muted-light)] bg-gray-100 px-2 py-0.5 rounded-full">
                        v{booth.version}
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRegenerateKey(booth.booth_id);
                      }}
                      className="p-1 text-[var(--muted-light)] hover:text-[var(--warm)] rounded transition opacity-0 group-hover:opacity-100"
                      title="Regenereer API key"
                    >
                      <Key className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteBooth(booth.booth_id);
                      }}
                      className="p-1 text-[var(--muted-light)] hover:text-[var(--danger)] rounded transition opacity-0 group-hover:opacity-100"
                      title="Verwijder booth"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Name */}
                <div
                  className="cursor-pointer"
                  onClick={() => router.push(`/booths/${booth.booth_id}`)}
                >
                  <h3 className="text-lg font-semibold text-[var(--foreground)] mb-1 group-hover:text-[var(--accent-dark)] transition">
                    {booth.name || booth.booth_id}
                  </h3>
                  <p className="text-xs text-[var(--muted-light)] font-mono mb-4">{booth.booth_id}</p>
                </div>

                {/* Event coupling */}
                <Select
                  label="Event"
                  value={booth.event_id || ""}
                  onChange={(e) => handleEventChange(booth.booth_id, e.target.value)}
                  wrapperClassName="mb-4"
                >
                  <option value="">Geen event</option>
                  {events
                    .filter((ev) => ev.is_active)
                    .map((ev) => (
                      <option key={ev.id} value={ev.id}>
                        {ev.name}
                      </option>
                    ))}
                </Select>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <p className="text-xs text-[var(--muted-light)] mb-0.5 flex items-center gap-1">
                      <Cpu className="w-3 h-3" /> CPU
                    </p>
                    <p className="text-sm font-medium text-[var(--foreground)]">
                      {booth.cpu_percent != null ? `${booth.cpu_percent}%` : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-[var(--muted-light)] mb-0.5 flex items-center gap-1">
                      <Camera className="w-3 h-3" /> Camera
                    </p>
                    <p className="text-sm font-medium">
                      {booth.camera_connected ? (
                        <Check className="w-4 h-4 text-emerald-500 inline" />
                      ) : (
                        <XIcon className="w-4 h-4 text-[var(--muted-light)] inline" />
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-[var(--muted-light)] mb-0.5 flex items-center gap-1">
                      <Clock className="w-3 h-3" /> Uptime
                    </p>
                    <p className="text-sm font-medium text-[var(--foreground)]">
                      {formatUptime(booth.uptime_seconds)}
                    </p>
                  </div>
                </div>

                {/* Last seen + event badge */}
                <div className="mt-4 pt-3 border-t border-[var(--card-border)] flex items-center justify-between">
                  <p className="text-xs text-[var(--muted-light)] flex items-center gap-1">
                    <Eye className="w-3 h-3" />
                    {formatLastSeen(booth.last_seen)}
                  </p>
                  {booth.event_id && (
                    <Badge variant="info">
                      {getEventName(booth.event_id)}
                    </Badge>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}

      {/* ---- Create Booth Modal ---- */}
      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="Nieuwe Booth"
        description="Registreer een nieuw photobooth device"
        actions={
          <>
            <Button variant="ghost" onClick={() => setShowCreate(false)}>
              Annuleren
            </Button>
            <Button
              variant="primary"
              onClick={handleCreateBooth}
              disabled={!createForm.booth_id.trim()}
              loading={creating}
            >
              Registreren
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Input
            label="Booth ID *"
            value={createForm.booth_id}
            onChange={(e) =>
              setCreateForm({ ...createForm, booth_id: e.target.value })
            }
            placeholder="bv. booth-001"
            helper="Unieke identifier — gebruik in booth.toml"
            className="font-mono"
            autoFocus
          />
          <Input
            label="Naam"
            value={createForm.name}
            onChange={(e) =>
              setCreateForm({ ...createForm, name: e.target.value })
            }
            placeholder="bv. Photobooth Lobby"
          />
        </div>
      </Modal>

      {/* ---- API Key Display Modal ---- */}
      <Modal
        open={!!apiKeyInfo}
        onClose={() => setApiKeyInfo(null)}
        title="API Key"
        description={apiKeyInfo?.booth_id}
        actions={
          <Button variant="primary" onClick={() => setApiKeyInfo(null)}>
            Begrepen, sluiten
          </Button>
        }
      >
        {apiKeyInfo && (
          <>
            <div className="bg-[var(--warning-light)] border border-amber-200 rounded-lg p-4 mb-4">
              <p className="text-xs text-amber-700 mb-2 font-medium flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                Deze key wordt maar één keer getoond!
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-sm text-[var(--foreground)] font-mono break-all bg-white p-2 rounded border border-amber-200">
                  {apiKeyInfo.api_key}
                </code>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(apiKeyInfo.api_key);
                    showToast("API key gekopieerd");
                  }}
                  className="shrink-0 p-2 text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-gray-100 rounded-lg transition"
                  title="Kopieer"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="bg-gray-50 rounded-lg p-3 border border-[var(--card-border)]">
              <p className="text-xs text-[var(--muted)] mb-1">Configureer in booth.toml:</p>
              <code className="text-xs text-[var(--foreground)] font-mono">
                [server]<br />
                booth_id = &quot;{apiKeyInfo.booth_id}&quot;<br />
                api_key = &quot;{apiKeyInfo.api_key}&quot;
              </code>
            </div>
          </>
        )}
      </Modal>

      {/* ---- Toast ---- */}
      {toast && (
        <Toast
          message={toast}
          onDismiss={() => setToast("")}
        />
      )}
    </>
  );
}
