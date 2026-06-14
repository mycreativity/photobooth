"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { authFetch, getAccessToken, clearTokens, isLoggedIn } from "@/lib/auth";
import PageHeader from "@/app/components/PageHeader";
import { Cpu, Thermometer, MemoryStick, HardDrive, Clock, RotateCw, Power, ChevronDown, RefreshCw, Server, Terminal, Check, X, CalendarDays, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";

interface BoothInfo {
  id: string;
  booth_id: string;
  name: string | null;
  event_id: string | null;
  status: string;
  last_seen: string | null;
  version: string | null;
  // System metrics
  cpu_percent: number | null;
  camera_connected: boolean;
  uptime_seconds: number | null;
  mem_total_mb: number;
  mem_used_mb: number;
  mem_percent: number;
  cpu_temp: number | null;
  disk_total_gb: number;
  disk_used_gb: number;
  disk_free_gb: number;
  disk_percent: number;
  hostname: string;
  platform: string;
  python: string;
  // Power / electricity
  power_voltage: number | null;
  power_current_a: number | null;
  power_watts: number | null;
  power_throttled: string | null;
  settings: Record<string, unknown>;
}

interface EventOption {
  id: string;
  uid: string;
  name: string;
  is_active: boolean;
}

interface BoothEventState {
  event_uid: string;
  event_name: string;
  display_date: string;
  updated_at: string;
}

function formatUptime(seconds: number | null): string {
  if (!seconds) return "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}u ${m}m`;
  return h > 0 ? `${h}u ${m}m` : `${m}m`;
}

function formatLastSeen(iso: string | null): string {
  if (!iso) return "Nooit";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  if (diff < 60_000) return "Nu";
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m geleden`;
  return d.toLocaleString("nl-NL");
}

function ProgressBar({ percent, color = "teal" }: { percent: number; color?: string }) {
  const colorMap: Record<string, string> = {
    teal: "bg-[var(--accent)]",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    red: "bg-red-500",
  };
  const barColor = percent > 85 ? colorMap.red : percent > 60 ? colorMap.amber : colorMap[color] || colorMap.teal;
  return (
    <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden mt-1">
      <div className={`h-full ${barColor} rounded-full transition-all duration-500`} style={{ width: `${Math.min(percent, 100)}%` }} />
    </div>
  );
}

export default function BoothDetailPage({
  params,
}: {
  params: Promise<{ boothId: string }>;
}) {
  const router = useRouter();
  const [booth, setBooth] = useState<BoothInfo | null>(null);
  const [events, setEvents] = useState<EventOption[]>([]);
  const [loading, setLoading] = useState(true);
  // Event sync
  const [syncOpen, setSyncOpen] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"running" | "done" | "error">("running");
  const [syncSteps, setSyncSteps] = useState<Array<{ step: string; label: string }>>([]);
  const [syncError, setSyncError] = useState("");
  const [syncEventName, setSyncEventName] = useState("");
  const [boothEventState, setBoothEventState] = useState<BoothEventState | null>(null);
  const [error, setError] = useState("");
  const [boothId, setBoothId] = useState<string>("");
  const [logs, setLogs] = useState<Array<{level: string; message: string; logger: string; ts: string}>>([])
  const logEndRef = useRef<HTMLDivElement | null>(null);
  const logWsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    params.then((p) => setBoothId(p.boothId));
  }, [params, router]);

  useEffect(() => {
    if (!boothId) return;
    fetchBooth();
    fetchEvents();
    const interval = setInterval(fetchBooth, 5_000);
    return () => clearInterval(interval);
  }, [boothId]);

  useEffect(() => { return () => {
    if (logWsRef.current) logWsRef.current.close();
  }; }, []);

  // Load initial logs + start streaming
  useEffect(() => {
    if (!boothId) return;
    fetchInitialLogs();
    startLogStream();
    return () => { if (logWsRef.current) logWsRef.current.close(); };
  }, [boothId]);

  // Auto-scroll log panel
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  async function fetchBooth() {
    try {
      const res = await authFetch(`/api/api/booths/${boothId}/info`);
      if (res.status === 401) { clearTokens(); router.replace("/login"); return; }
      if (!res.ok) throw new Error("Booth not found");
      setBooth(await res.json());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  async function fetchEvents() {
    try {
      const res = await authFetch("/api/api/events");
      if (res.ok) setEvents(await res.json());
    } catch {}
  }

  async function handleEventChange(eventId: string) {
    // Clearing the coupling needs no device sync.
    if (!eventId) {
      try {
        const res = await authFetch(`/api/api/booths/${boothId}/sync-event`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ event_id: null }),
        });
        if (!res.ok) throw new Error("Loskoppelen mislukt");
        fetchBooth();
      } catch (err) {
        alert(err instanceof Error ? err.message : "Loskoppelen mislukt");
      }
      return;
    }

    // Coupling: push to booth and only persist after a confirmed sync.
    const ev = events.find((e) => e.id === eventId);
    setSyncEventName(ev?.name || "");
    setSyncSteps([]);
    setSyncError("");
    setSyncStatus("running");
    setSyncOpen(true);

    try {
      const res = await authFetch(`/api/api/booths/${boothId}/sync-event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: eventId }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Synchronisatie mislukt");
      }
      setSyncStatus("done");
      await fetchBooth();
    } catch (err) {
      setSyncStatus("error");
      setSyncError(err instanceof Error ? err.message : "Synchronisatie mislukt");
      fetchBooth(); // revert the dropdown to the last persisted value
    }
  }

  async function fetchInitialLogs() {
    try {
      const res = await authFetch(`/api/api/booths/${boothId}/logs?limit=100`);
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch {}
  }

  function startLogStream() {
    const token = getAccessToken();
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const ws = new WebSocket(`${wsUrl}/ws/admin/${boothId}?token=${token}`);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "log") {
          setLogs(prev => {
            const next = [...prev, { level: msg.level, message: msg.message, logger: msg.logger, ts: msg.ts }];
            return next.length > 200 ? next.slice(-200) : next;
          });
        } else if (msg.type === "sync_progress") {
          setSyncSteps(prev => [...prev, { step: msg.step || "", label: msg.label || "" }]);
        } else if (msg.type === "event_state") {
          setBoothEventState({
            event_uid: msg.event_uid || "",
            event_name: msg.event_name || "",
            display_date: msg.display_date || "",
            updated_at: msg.updated_at || "",
          });
        }
      } catch {}
    };
    logWsRef.current = ws;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-4 border-[var(--accent)]/30 border-t-[var(--accent)] rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !booth) {
    return (
      <div className="text-center py-20">
        <p className="text-[var(--danger)] mb-4">{error || "Booth not found"}</p>
        <button onClick={() => router.push("/")} className="px-6 py-2 bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white rounded-xl transition">← Terug</button>
      </div>
    );
  }

  const isOnline = booth.status === "online";

  return (
    <div className="space-y-6">
      <PageHeader
        title={booth.name || booth.booth_id}
        subtitle={booth.booth_id}
        backHref="/"
        badge={
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${isOnline ? "bg-emerald-500 animate-pulse" : "bg-gray-300"}`} />
            <span className="text-sm text-[var(--muted)]">{isOnline ? "Online" : "Offline"}</span>
          </div>
        }
        actions={
          <div className="flex items-center gap-2">
            <RestartControl boothId={boothId} isOnline={isOnline} />
            <button onClick={() => fetchBooth()} className="flex items-center px-2.5 py-2 text-[var(--muted)] hover:text-[var(--foreground)] bg-white hover:bg-gray-50 rounded-lg border border-[var(--card-border)] transition" title="Refresh"><RefreshCw className="w-4 h-4" /></button>
          </div>
        }
      />

      {/* Stats — combined into one block. Live metrics are only meaningful while online */}
      <div className="bg-white border border-[var(--card-border)] rounded-2xl p-5">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-x-6 gap-y-5 divide-y divide-[var(--card-border)] md:divide-y-0 md:divide-x">
          <Metric icon={<Cpu />} label="CPU" value={isOnline ? `${booth.cpu_percent ?? 0}%` : "—"} online={isOnline} percent={booth.cpu_percent ?? 0} />
          <Metric icon={<Thermometer />} label="Temperatuur" value={isOnline && booth.cpu_temp != null ? `${booth.cpu_temp}°C` : "—"} online={isOnline} valueColor={booth.cpu_temp && booth.cpu_temp > 70 ? "text-red-600" : booth.cpu_temp && booth.cpu_temp > 55 ? "text-amber-600" : undefined} />
          <Metric icon={<MemoryStick />} label="Geheugen" value={isOnline ? `${booth.mem_used_mb} / ${booth.mem_total_mb} MB` : "—"} online={isOnline} percent={booth.mem_percent} percentColor="teal" />
          <Metric icon={<HardDrive />} label="Schijf" value={isOnline ? `${booth.disk_used_gb} / ${booth.disk_total_gb} GB` : "—"} online={isOnline} percent={booth.disk_percent} percentColor="emerald" />
          <Metric icon={<Clock />} label="Uptime" value={isOnline ? formatUptime(booth.uptime_seconds) : "—"} online={isOnline} />
        </div>
      </div>

      {/* Event coupling */}
      <div className="bg-white border border-[var(--card-border)] rounded-2xl p-6">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-[var(--foreground)] mb-4">
          <CalendarDays className="w-[18px] h-[18px] text-[var(--muted)]" />
          Event
        </h2>
        <div className="flex flex-col sm:flex-row gap-4 items-start">
          {/* Select */}
          <div className="relative w-full sm:max-w-xs">
            <select
              value={booth.event_id || ""}
              onChange={(e) => handleEventChange(e.target.value)}
              className="w-full appearance-none bg-white border border-[var(--input-border)] rounded-lg pl-3 pr-9 py-2 text-sm text-[var(--foreground)] cursor-pointer focus:outline-none focus:border-[var(--primary)] focus:ring-2 focus:ring-[var(--primary)]/15 transition"
            >
              <option value="">Geen event</option>
              {events
                .filter((ev) => ev.is_active || ev.id === booth.event_id)
                .map((ev) => (
                  <option key={ev.id} value={ev.id}>
                    {ev.name}
                  </option>
                ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted-light)]" />
          </div>

          {/* Booth live state */}
          <BoothEventPanel state={boothEventState} isOnline={isOnline} />
        </div>
      </div>

      {/* Device info */}
      <div className="bg-white border border-[var(--card-border)] rounded-2xl p-6">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-[var(--foreground)] mb-4">
          <Server className="w-[18px] h-[18px] text-[var(--muted)]" />
          Apparaat
        </h2>
        <dl className="grid sm:grid-cols-2 gap-x-10 gap-y-3">
          <InfoRow label="Booth ID" value={booth.booth_id} />
          <InfoRow label="Naam" value={booth.name || "—"} />
          <InfoRow
            label="Camera"
            value={
              booth.camera_connected ? (
                <span className="inline-flex items-center gap-1 text-emerald-600">
                  <Check className="w-4 h-4" /> Verbonden
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[var(--muted)]">
                  <X className="w-4 h-4" /> Geen
                </span>
              )
            }
          />
          <InfoRow label="Versie" value={booth.version ? `v${booth.version}` : "—"} />
          <InfoRow label="Hostname" value={booth.hostname || "—"} />
          <InfoRow label="Platform" value={booth.platform || "—"} />
          <InfoRow label="Python" value={booth.python || "—"} />
          <InfoRow label="Laatst gezien" value={formatLastSeen(booth.last_seen)} />
        </dl>
      </div>

        {/* Log panel — full width */}
        <div className="bg-white border border-[var(--card-border)] rounded-2xl p-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-[var(--foreground)]">
              <Terminal className="w-[18px] h-[18px] text-[var(--muted)]" />
              Logs
            </h2>
            <button onClick={() => { setLogs([]); fetchInitialLogs(); }} className="text-xs text-[var(--muted-light)] hover:text-[var(--foreground)] transition">Clear</button>
          </div>
          <div className="bg-gray-50 rounded-xl p-3 h-72 overflow-y-auto font-mono text-xs leading-relaxed scrollbar-thin border border-[var(--card-border)]">
            {logs.length === 0 ? (
              <p className="text-[var(--muted-light)] text-center py-8">Geen logs beschikbaar</p>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="flex gap-2 py-0.5 hover:bg-gray-100 rounded">
                  <span className="text-[var(--muted-light)] shrink-0 w-20">{log.ts ? new Date(log.ts).toLocaleTimeString("nl-NL") : ""}</span>
                  <LogLevel level={log.level} />
                  <span className="text-[var(--muted-light)] shrink-0 w-28 truncate" title={log.logger}>{log.logger?.split(".").pop()}</span>
                  <span className="text-[var(--foreground)] break-all">{log.message}</span>
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>

        {/* Event sync overlay */}
        {syncOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4">
            <div className="bg-white border border-[var(--card-border)] rounded-xl w-full max-w-md p-6">
              <div className="flex items-center gap-2.5 mb-1">
                {syncStatus === "running" && <Loader2 className="w-5 h-5 animate-spin text-[var(--primary)]" />}
                {syncStatus === "done" && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                {syncStatus === "error" && <AlertTriangle className="w-5 h-5 text-[var(--danger)]" />}
                <h3 className="text-base font-semibold text-[var(--foreground)]">
                  {syncStatus === "error"
                    ? "Synchronisatie mislukt"
                    : syncStatus === "done"
                    ? "Gesynchroniseerd"
                    : "Event synchroniseren"}
                </h3>
              </div>
              <p className="text-sm text-[var(--muted)] mb-4 pl-[30px]">
                {syncEventName} → {booth.name || booth.booth_id}
              </p>

              <ul className="space-y-2">
                {syncSteps.map((s, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-[var(--foreground)]">
                    <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                    {s.label}
                  </li>
                ))}
                {syncStatus === "running" && (
                  <li className="flex items-center gap-2 text-sm text-[var(--muted)]">
                    <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                    Wachten op booth…
                  </li>
                )}
              </ul>

              {syncStatus === "error" && (
                <p className="mt-4 text-sm text-[var(--danger)] bg-[var(--danger-light)] border border-red-200 rounded-lg p-3">
                  {syncError}
                </p>
              )}

              {syncStatus !== "running" && (
                <div className="flex justify-end mt-5">
                  <button
                    onClick={() => setSyncOpen(false)}
                    className="px-4 py-2 text-sm font-medium bg-[var(--primary)] hover:bg-[var(--primary-dark)] text-white rounded-lg transition"
                  >
                    Sluiten
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
  online,
  percent,
  percentColor = "teal",
  valueColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  online: boolean;
  percent?: number;
  percentColor?: string;
  valueColor?: string;
}) {
  return (
    <div className="md:px-5 first:pl-0 last:pr-0 pt-5 first:pt-0 md:pt-0">
      <div className="flex items-center gap-1.5 text-[var(--muted-light)] mb-1.5 [&>svg]:w-3.5 [&>svg]:h-3.5">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <p className={`text-lg font-semibold ${online ? valueColor || "text-[var(--foreground)]" : "text-[var(--muted-light)]"}`}>
        {value}
      </p>
      {online && percent !== undefined && <ProgressBar percent={percent} color={percentColor} />}
    </div>
  );
}

function RestartControl({ boothId, isOnline }: { boothId: string; isOnline: boolean }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  async function send(kind: "restart" | "reboot") {
    setOpen(false);
    const prompts: Record<typeof kind, string> = {
      restart: "Weet je zeker dat je de photobooth-applicatie wilt herstarten?",
      reboot:
        "Weet je zeker dat je de hele Raspberry Pi wilt herstarten? De booth is dan ±1 minuut offline.",
    };
    if (!confirm(prompts[kind])) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/api/booths/${boothId}/${kind}`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Commando mislukt");
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Commando mislukt");
    } finally {
      setBusy(false);
    }
  }

  const disabled = !isOnline || busy;

  return (
    <div className="relative flex" ref={ref}>
      <button
        onClick={() => send("restart")}
        disabled={disabled}
        title={isOnline ? "Herstart de photobooth-applicatie" : "Booth is offline"}
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-l-lg bg-[var(--warning-light)] text-amber-700 border border-amber-200 hover:bg-amber-100 transition disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <RotateCw className="w-4 h-4" />
        Herstart app
      </button>
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        title="Meer herstart-opties"
        className="flex items-center px-1.5 py-1.5 rounded-r-lg bg-[var(--warning-light)] text-amber-700 border border-l-0 border-amber-200 hover:bg-amber-100 transition disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <ChevronDown className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-60 bg-white border border-[var(--card-border)] rounded-lg py-1 z-50">
          <button
            onClick={() => send("reboot")}
            className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-[var(--danger)] hover:bg-[var(--danger-light)] transition"
          >
            <Power className="w-4 h-4 shrink-0" />
            Herstart Raspberry Pi
          </button>
        </div>
      )}
    </div>
  );
}

function BoothEventPanel({ state, isOnline }: { state: BoothEventState | null; isOnline: boolean }) {
  if (!isOnline) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-50 border border-[var(--card-border)] text-sm text-[var(--muted-light)]">
        <span className="w-1.5 h-1.5 rounded-full bg-gray-300 shrink-0" />
        Booth offline
      </div>
    );
  }

  if (!state) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-50 border border-[var(--card-border)] text-sm text-[var(--muted-light)]">
        <span className="w-3 h-3 border-2 border-[var(--muted-light)] border-t-transparent rounded-full animate-spin shrink-0" />
        Wachten op booth…
      </div>
    );
  }

  const hasEvent = !!state.event_name;
  return (
    <div className="flex items-start gap-2.5 px-3.5 py-2.5 rounded-lg bg-gray-50 border border-[var(--card-border)] min-w-0">
      <span className={`mt-0.5 w-1.5 h-1.5 rounded-full shrink-0 ${hasEvent ? "bg-emerald-500" : "bg-gray-300"}`} />
      <div className="min-w-0">
        <p className="text-[11px] text-[var(--muted-light)] mb-0.5 leading-none">Op booth geconfigureerd</p>
        {hasEvent ? (
          <>
            <p className="text-sm font-medium text-[var(--foreground)] truncate">{state.event_name}</p>
            {state.display_date && (
              <p className="text-xs text-[var(--muted)] truncate">{state.display_date}</p>
            )}
            {state.event_uid && (
              <p className="text-[11px] text-[var(--muted-light)] font-mono truncate">ID: {state.event_uid}</p>
            )}
          </>
        ) : (
          <p className="text-sm text-[var(--muted)]">Geen event</p>
        )}
        {state.updated_at && (
          <p className="text-[10px] text-[var(--muted-light)] mt-1">
            {new Date(state.updated_at).toLocaleString("nl-NL", { dateStyle: "short", timeStyle: "short" })}
          </p>
        )}
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-start gap-2">
      <dt className="text-sm text-[var(--muted)]">{label}</dt>
      <dd className="text-sm text-[var(--foreground)] font-medium text-right break-all">{value}</dd>
    </div>
  );
}

function LogLevel({ level }: { level: string }) {
  const colors: Record<string, string> = {
    DEBUG: "text-gray-400",
    INFO: "text-blue-600",
    WARNING: "text-amber-600",
    ERROR: "text-red-600",
    CRITICAL: "text-red-700 font-bold",
  };
  return (
    <span className={`shrink-0 w-14 ${colors[level] || colors.INFO}`}>
      {level}
    </span>
  );
}
