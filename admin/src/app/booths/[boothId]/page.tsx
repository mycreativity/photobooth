"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { authFetch, getAccessToken, clearTokens, isLoggedIn } from "@/lib/auth";

interface BoothInfo {
  id: string;
  booth_id: string;
  name: string | null;
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
  settings: Record<string, unknown>;
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

function ProgressBar({ percent, color = "violet" }: { percent: number; color?: string }) {
  const colorMap: Record<string, string> = {
    violet: "bg-violet-500",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    red: "bg-red-500",
  };
  const barColor = percent > 85 ? colorMap.red : percent > 60 ? colorMap.amber : colorMap[color] || colorMap.violet;
  return (
    <div className="w-full h-2 bg-gray-700/50 rounded-full overflow-hidden mt-1">
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [boothId, setBoothId] = useState<string>("");
  const [previewing, setPreviewing] = useState(false);
  const [lastFrame, setLastFrame] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [logs, setLogs] = useState<Array<{level: string; message: string; logger: string; ts: string}>>([])
  const [logStreaming, setLogStreaming] = useState(false);
  const logEndRef = useRef<HTMLDivElement | null>(null);
  const logWsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    params.then((p) => setBoothId(p.boothId));
  }, [params, router]);

  useEffect(() => {
    if (!boothId) return;
    fetchBooth();
    const interval = setInterval(fetchBooth, 5_000);
    return () => clearInterval(interval);
  }, [boothId]);

  useEffect(() => { return () => {
    if (wsRef.current) wsRef.current.close();
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

  function togglePreview() { previewing ? stopPreview() : startPreview(); }

  function startPreview() {
    const token = getAccessToken();
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const ws = new WebSocket(`${wsUrl}/ws/admin/${boothId}?token=${token}`);
    ws.onopen = () => { setPreviewing(true); ws.send(JSON.stringify({ type: "start_preview" })); };
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "frame" && msg.data) setLastFrame(`data:image/jpeg;base64,${msg.data}`);
      } catch {}
    };
    ws.onclose = () => setPreviewing(false);
    wsRef.current = ws;
  }

  function stopPreview() {
    if (wsRef.current) { wsRef.current.send(JSON.stringify({ type: "stop_preview" })); wsRef.current.close(); wsRef.current = null; }
    setPreviewing(false); setLastFrame(null);
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
    ws.onopen = () => setLogStreaming(true);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "log") {
          setLogs(prev => {
            const next = [...prev, { level: msg.level, message: msg.message, logger: msg.logger, ts: msg.ts }];
            return next.length > 200 ? next.slice(-200) : next;
          });
        }
      } catch {}
    };
    ws.onclose = () => setLogStreaming(false);
    logWsRef.current = ws;
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950">
        <div className="w-8 h-8 border-4 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !booth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error || "Booth not found"}</p>
          <button onClick={() => router.push("/")} className="px-6 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl transition">← Terug</button>
        </div>
      </div>
    );
  }

  const isOnline = booth.status === "online";
  const settings = booth.settings || {};

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800/50 bg-gray-900/50 backdrop-blur-xl sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => router.push("/")} className="text-gray-400 hover:text-white transition mr-2">←</button>
            <span className="text-2xl">📸</span>
            <div>
              <h1 className="text-xl font-bold text-white">{booth.name || booth.booth_id}</h1>
              <p className="text-xs text-gray-500 font-mono">{booth.booth_id}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => fetchBooth()} className="px-3 py-1.5 text-sm text-gray-400 hover:text-white bg-gray-800/50 hover:bg-gray-700/50 rounded-lg border border-gray-700/30 transition" title="Refresh">↻</button>
            <span className={`w-2.5 h-2.5 rounded-full ${isOnline ? "bg-emerald-500 shadow-lg shadow-emerald-500/50 animate-pulse" : "bg-gray-600"}`} />
            <span className="text-sm text-gray-300">{isOnline ? "Online" : "Offline"}</span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">

        {/* Top stats row */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <MetricCard label="CPU" value={`${booth.cpu_percent ?? 0}%`} sub={<ProgressBar percent={booth.cpu_percent ?? 0} />} />
          <MetricCard label="Temperatuur" value={booth.cpu_temp != null ? `${booth.cpu_temp}°C` : "—"} color={booth.cpu_temp && booth.cpu_temp > 70 ? "red" : booth.cpu_temp && booth.cpu_temp > 55 ? "amber" : "emerald"} />
          <MetricCard label="Geheugen" value={`${booth.mem_used_mb} / ${booth.mem_total_mb} MB`} sub={<ProgressBar percent={booth.mem_percent} color="violet" />} />
          <MetricCard label="Schijf" value={`${booth.disk_used_gb} / ${booth.disk_total_gb} GB`} sub={<ProgressBar percent={booth.disk_percent} color="emerald" />} />
          <MetricCard label="Uptime" value={formatUptime(booth.uptime_seconds)} />
        </div>

        {/* Main content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Device info */}
          <div className="bg-gray-800/30 border border-gray-700/30 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4">📋 Apparaat</h2>
            <dl className="space-y-3">
              <InfoRow label="Booth ID" value={booth.booth_id} />
              <InfoRow label="Naam" value={booth.name || "—"} />
              <InfoRow label="Status" value={isOnline ? "🟢 Online" : "⚫ Offline"} />
              <InfoRow label="Camera" value={booth.camera_connected ? "✓ Verbonden" : "✗ Geen"} />
              <InfoRow label="Versie" value={booth.version ? `v${booth.version}` : "—"} />
              <InfoRow label="Hostname" value={booth.hostname || "—"} />
              <InfoRow label="Platform" value={booth.platform || "—"} />
              <InfoRow label="Python" value={booth.python || "—"} />
              <InfoRow label="Laatst gezien" value={formatLastSeen(booth.last_seen)} />
            </dl>
          </div>

          {/* Live camera */}
          <div className="bg-gray-800/30 border border-gray-700/30 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">📷 Camera</h2>
              <button onClick={togglePreview} disabled={!isOnline}
                className={`px-4 py-1.5 text-sm font-medium rounded-lg transition ${previewing ? "bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30" : "bg-violet-600/20 text-violet-400 hover:bg-violet-600/30 border border-violet-500/30"} disabled:opacity-30 disabled:cursor-not-allowed`}>
                {previewing ? "⏹ Stop" : "▶ Live"}
              </button>
            </div>
            <div className="aspect-video bg-gray-900/50 rounded-xl overflow-hidden flex items-center justify-center">
              {lastFrame ? (
                <img src={lastFrame} alt="Live camera feed" className="w-full h-full object-contain" />
              ) : (
                <div className="text-center text-gray-600">
                  <p className="text-3xl mb-2">📷</p>
                  <p className="text-sm">{isOnline ? "Klik ▶ voor live preview" : "Booth is offline"}</p>
                </div>
              )}
            </div>
          </div>

          {/* Settings Editor */}
          <SettingsPanel settings={settings} boothId={boothId} isOnline={isOnline} onSaved={fetchBooth} />
        </div>

        {/* Log panel — full width */}
        <div className="bg-gray-800/30 border border-gray-700/30 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-white">📜 Logs</h2>
            <div className="flex items-center gap-3">
              <span className={`flex items-center gap-1.5 text-xs ${logStreaming ? "text-emerald-400" : "text-gray-500"}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${logStreaming ? "bg-emerald-500 animate-pulse" : "bg-gray-600"}`} />
                {logStreaming ? "Live" : "Offline"}
              </span>
              <button onClick={() => { setLogs([]); fetchInitialLogs(); }} className="text-xs text-gray-500 hover:text-gray-300 transition">Clear</button>
            </div>
          </div>
          <div className="bg-gray-950/50 rounded-xl p-3 h-72 overflow-y-auto font-mono text-xs leading-relaxed scrollbar-thin">
            {logs.length === 0 ? (
              <p className="text-gray-600 text-center py-8">Geen logs beschikbaar</p>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="flex gap-2 py-0.5 hover:bg-gray-800/30">
                  <span className="text-gray-600 shrink-0 w-20">{log.ts ? new Date(log.ts).toLocaleTimeString("nl-NL") : ""}</span>
                  <LogLevel level={log.level} />
                  <span className="text-gray-500 shrink-0 w-28 truncate" title={log.logger}>{log.logger?.split(".").pop()}</span>
                  <span className="text-gray-300 break-all">{log.message}</span>
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      </main>
    </div>
  );
}

function MetricCard({ label, value, sub, color = "violet" }: { label: string; value: string; sub?: React.ReactNode; color?: string }) {
  const colorMap: Record<string, string> = { emerald: "text-emerald-400", red: "text-red-400", amber: "text-amber-400", violet: "text-violet-300", gray: "text-gray-400" };
  return (
    <div className="bg-gray-800/30 border border-gray-700/30 rounded-xl p-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-lg font-semibold ${colorMap[color] || colorMap.violet}`}>{value}</p>
      {sub}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-start gap-2">
      <dt className="text-sm text-gray-500 shrink-0">{label}</dt>
      <dd className="text-sm text-gray-300 font-medium text-right break-all">{value}</dd>
    </div>
  );
}

function LogLevel({ level }: { level: string }) {
  const colors: Record<string, string> = {
    DEBUG: "text-gray-500",
    INFO: "text-blue-400",
    WARNING: "text-amber-400",
    ERROR: "text-red-400",
    CRITICAL: "text-red-300 font-bold",
  };
  return (
    <span className={`shrink-0 w-14 ${colors[level] || colors.INFO}`}>
      {level}
    </span>
  );
}

function SettingsPanel({
  settings,
  boothId,
  isOnline,
  onSaved,
}: {
  settings: Record<string, unknown>;
  boothId: string;
  isOnline: boolean;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "ok" | "error"; msg: string } | null>(null);

  // Init form from live settings
  useEffect(() => {
    if (Object.keys(settings).length > 0 && Object.keys(form).length === 0) {
      setForm({ ...settings });
    }
  }, [settings]);

  function update(key: string, value: unknown) {
    setForm(prev => ({ ...prev, [key]: value }));
    setStatus(null);
  }

  async function save() {
    setSaving(true);
    setStatus(null);
    try {
      const res = await authFetch(`/api/api/booths/${boothId}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed");
      }
      setStatus({ type: "ok", msg: "Opgeslagen ✓" });
      setTimeout(() => onSaved(), 2000);
    } catch (err) {
      setStatus({ type: "error", msg: err instanceof Error ? err.message : "Error" });
    } finally {
      setSaving(false);
    }
  }

  async function restart() {
    if (!confirm("Wil je de booth herstarten?")) return;
    try {
      await authFetch(`/api/api/booths/${boothId}/restart`, { method: "POST" });
      setStatus({ type: "ok", msg: "Herstart verzonden" });
    } catch {
      setStatus({ type: "error", msg: "Herstart mislukt" });
    }
  }

  const inputClass = "w-full bg-gray-900/50 border border-gray-700/40 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:border-violet-500/50 focus:outline-none transition";
  const labelClass = "text-xs text-gray-500 mb-0.5";

  if (Object.keys(settings).length === 0) {
    return (
      <div className="bg-gray-800/30 border border-gray-700/30 rounded-2xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">⚙️ Instellingen</h2>
        <p className="text-gray-500 text-sm">Wachten op heartbeat data...</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800/30 border border-gray-700/30 rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">⚙️ Instellingen</h2>
        {status && (
          <span className={`text-xs px-2 py-0.5 rounded ${status.type === "ok" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
            {status.msg}
          </span>
        )}
      </div>

      <div className="space-y-3">
        {/* Event */}
        <div>
          <label className={labelClass}>Event naam</label>
          <input className={inputClass} value={String(form.event_name || "")} onChange={e => update("event_name", e.target.value)} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>Taal</label>
            <select className={inputClass} value={String(form.language || "nl")} onChange={e => update("language", e.target.value)}>
              <option value="nl">NL</option>
              <option value="en">EN</option>
              <option value="de">DE</option>
              <option value="fr">FR</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>Thema</label>
            <select className={inputClass} value={String(form.theme || "classic")} onChange={e => update("theme", e.target.value)}>
              <option value="classic">Classic</option>
              <option value="neon">Neon</option>
              <option value="elegant">Elegant</option>
            </select>
          </div>
        </div>

        <div className="border-t border-gray-700/30 my-1" />

        {/* Camera */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>Camera</label>
            <select className={inputClass} value={String(form.camera_backend || "gphoto2")} onChange={e => update("camera_backend", e.target.value)}>
              <option value="gphoto2">DSLR (gPhoto2)</option>
              <option value="webcam">Webcam</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>ISO</label>
            <input className={inputClass} value={String(form.camera_iso || "")} onChange={e => update("camera_iso", e.target.value)} placeholder="auto" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>Diafragma</label>
            <input className={inputClass} value={String(form.camera_aperture || "")} onChange={e => update("camera_aperture", e.target.value)} placeholder="auto" />
          </div>
          <div>
            <label className={labelClass}>Sluitertijd</label>
            <input className={inputClass} value={String(form.camera_shutter || "")} onChange={e => update("camera_shutter", e.target.value)} placeholder="auto" />
          </div>
        </div>

        <div className="border-t border-gray-700/30 my-1" />

        {/* Countdown */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>1e Countdown (sec)</label>
            <input type="number" className={inputClass} value={Number(form.first_countdown || 5)} onChange={e => update("first_countdown", parseInt(e.target.value) || 5)} min={1} max={30} />
          </div>
          <div>
            <label className={labelClass}>Tussenpauze (sec)</label>
            <input type="number" className={inputClass} value={Number(form.between_shots || 3)} onChange={e => update("between_shots", parseInt(e.target.value) || 3)} min={1} max={30} />
          </div>
        </div>

        <div className="border-t border-gray-700/30 my-1" />

        {/* LEDs */}
        <div className="grid grid-cols-2 gap-3">
          <div className="flex items-center gap-2">
            <input type="checkbox" id="led-toggle" className="accent-violet-500" checked={!!form.led_enabled} onChange={e => update("led_enabled", e.target.checked)} />
            <label htmlFor="led-toggle" className="text-sm text-gray-400">LEDs aan</label>
          </div>
          <div>
            <label className={labelClass}>Helderheid (0-255)</label>
            <input type="number" className={inputClass} value={Number(form.led_brightness || 100)} onChange={e => update("led_brightness", parseInt(e.target.value) || 100)} min={0} max={255} />
          </div>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 mt-5">
        <button onClick={save} disabled={!isOnline || saving}
          className="flex-1 py-2 text-sm font-medium bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition disabled:opacity-30 disabled:cursor-not-allowed">
          {saving ? "Opslaan..." : "💾 Opslaan"}
        </button>
        <button onClick={restart} disabled={!isOnline}
          className="px-4 py-2 text-sm font-medium bg-amber-600/20 hover:bg-amber-600/30 text-amber-400 border border-amber-500/30 rounded-lg transition disabled:opacity-30 disabled:cursor-not-allowed">
          🔄 Herstart
        </button>
      </div>
    </div>
  );
}
