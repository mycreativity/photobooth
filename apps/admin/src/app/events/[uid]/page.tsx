"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { authFetch, clearTokens, isLoggedIn } from "@/lib/auth";
import PageHeader from "@/app/components/PageHeader";
import {
  Button, Input, Textarea, Tabs, Toggle, Modal, Toast, Card, Badge, Spinner,
} from "@/app/components/ui";
import {
  Save, Trash2, Settings, Palette, QrCode, Upload, Send,
  Check, Plus, Camera, ExternalLink, Copy,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface EventData {
  id: string;
  uid: string;
  name: string;
  description: string | null;
  date: string | null;
  end_date: string | null;
  is_active: boolean;
  background_image: string | null;
  branding_text: string | null;
  display_date: string | null;
  created_at: string;
  updated_at: string | null;
  photo_count?: number;
}

interface PresetBackground {
  name: string;
  label: string;
  url: string;
  exists: boolean;
}

type Tab = "general" | "photocard" | "sharing";
type PreviewLayout = "single" | "strip" | "grid";

const PUBLIC_BASE = "https://booth.mycreativity.nl/e";

/* ------------------------------------------------------------------ */
/*  Shared card layout constants (from shared/card_layout.json)        */
/* ------------------------------------------------------------------ */

const CARD = {
  canvas: { width: 1200, height: 1800 },
  padding: 20, // px at print resolution
  branding: {
    heightPercent: 15,
    accentLine: { thickness: 3, offsetTop: 8 },
    colors: { background: "#1C2028", text: "#EDE8D0", accent: "#FFFFFF" },
    fonts: { titleSize: 36, dateSize: 26, lineHeight: 42 },
  },
  layouts: {
    single: {
      label: "Portret",
      photosNeeded: 1,
      photoRatio: 0.8,
      slots: [{ x: 0, y: 6.0, w: 100, h: 88.0 }],
    },
    strip: {
      label: "Collage",
      photosNeeded: 3,
      photoRatio: 1.25,
      slots: [
        { x: 0, y: 2.9, w: 100, h: 62.0 },
        { x: 0, y: 66.9, w: 48.7, h: 30.2 },
        { x: 51.3, y: 66.9, w: 48.7, h: 30.2 },
      ],
    },
    grid: {
      label: "Mozaïek",
      photosNeeded: 6,
      photoRatio: 1.25,
      slots: [
        { x: 0, y: 2.9, w: 49.1, h: 30.5 },
        { x: 50.9, y: 2.9, w: 49.1, h: 30.5 },
        { x: 0, y: 34.8, w: 49.1, h: 30.5 },
        { x: 50.9, y: 34.8, w: 49.1, h: 30.5 },
        { x: 0, y: 66.6, w: 49.1, h: 30.5 },
        { x: 50.9, y: 66.6, w: 49.1, h: 30.5 },
      ],
    },
  },
} as const;

// Derived: padding as % of canvas height, photo area bounds
const PAD_PCT = (CARD.padding / CARD.canvas.height) * 100; // ~1.67%
const PHOTO_AREA_PCT = 100 - CARD.branding.heightPercent - 2 * PAD_PCT; // ~81.7%

/* ------------------------------------------------------------------ */
/*  Simple markdown → HTML                                             */
/* ------------------------------------------------------------------ */

function renderSimpleMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/__(.+?)__/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/_(.+?)_/g, "<em>$1</em>")
    .replace(/\n/g, "<br />");
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function EventDetailPage() {
  const router = useRouter();
  const params = useParams();
  const uid = params.uid as string;
  const isNew = uid === "new";

  const [event, setEvent] = useState<EventData | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [tab, setTab] = useState<Tab>("general");

  // Form state — general tab
  const [form, setForm] = useState({
    name: "",
    description: "",
    date: "",
    end_date: "",
    is_active: true,
  });
  const [saving, setSaving] = useState(false);

  // Photo card state
  const [presets, setPresets] = useState<PresetBackground[]>([]);
  const [selectedBg, setSelectedBg] = useState<string | null>(null);
  const [brandingText, setBrandingText] = useState("");
  const [displayDate, setDisplayDate] = useState("");
  const [bgVersion, setBgVersion] = useState(0);

  // Preview layout
  const [previewLayout, setPreviewLayout] = useState<PreviewLayout>("single");

  // Toast
  const [toast, setToast] = useState("");
  const showToast = useCallback((msg: string) => {
    setToast(msg);
  }, []);

  // Delete
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  /* ---- Fetch event ---- */
  const fetchEvent = useCallback(async () => {
    if (isNew) return;
    try {
      const res = await authFetch(`/api/api/events/${uid}`);
      if (res.status === 401) {
        clearTokens();
        router.replace("/login");
        return;
      }
      if (res.status === 404) {
        router.replace("/events");
        return;
      }
      if (!res.ok) throw new Error("Failed to fetch event");
      const data: EventData = await res.json();
      setEvent(data);

      // Populate form
      setForm({
        name: data.name,
        description: data.description || "",
        date: data.date ? data.date.slice(0, 16) : "",
        end_date: data.end_date ? data.end_date.slice(0, 16) : "",
        is_active: data.is_active,
      });

      // Populate photo card fields
      setSelectedBg(data.background_image);
      setBrandingText(
        data.branding_text || `**${data.name}** ✨\n_Wat een feest!_`
      );
      setDisplayDate(data.display_date || "");
    } catch {
      router.replace("/events");
    } finally {
      setLoading(false);
    }
  }, [uid, isNew, router]);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    fetchEvent();
  }, [router, fetchEvent]);

  // Fetch preset backgrounds
  useEffect(() => {
    (async () => {
      try {
        const res = await authFetch("/api/api/events/presets/backgrounds");
        if (res.ok) setPresets(await res.json());
      } catch {
        /* ignore */
      }
    })();
  }, []);

  // Auto-generate Dutch date from event date
  useEffect(() => {
    if (!displayDate && form.date) {
      const d = new Date(form.date);
      const days = [
        "Zondag", "Maandag", "Dinsdag", "Woensdag",
        "Donderdag", "Vrijdag", "Zaterdag",
      ];
      const months = [
        "Januari", "Februari", "Maart", "April", "Mei", "Juni",
        "Juli", "Augustus", "September", "Oktober", "November", "December",
      ];
      if (!isNaN(d.getTime())) {
        setDisplayDate(
          `${days[d.getDay()]} ${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`
        );
      }
    }
  }, [displayDate, form.date]);

  /* ---- Save (create or update) ---- */
  async function handleSave() {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        name: form.name,
        description: form.description || null,
        is_active: form.is_active,
        branding_text: brandingText || null,
        display_date: displayDate || null,
      };
      if (form.date) body.date = new Date(form.date).toISOString();
      if (form.end_date) body.end_date = new Date(form.end_date).toISOString();

      if (isNew) {
        const res = await authFetch("/api/api/events", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Aanmaken mislukt");
        }
        const created: EventData = await res.json();
        showToast("Event aangemaakt");
        router.replace(`/events/${created.uid}`);
      } else {
        const res = await authFetch(`/api/api/events/${uid}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error("Opslaan mislukt");
        showToast("Event opgeslagen");
        await fetchEvent();
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  }

  /* ---- Delete ---- */
  async function handleDelete() {
    setDeleting(true);
    try {
      const res = await authFetch(`/api/api/events/${uid}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Verwijderen mislukt");
      showToast("Event verwijderd");
      router.replace("/events");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
      setDeleting(false);
    }
  }

  /* ---- Background functions ---- */
  async function selectPreset(presetName: string) {
    try {
      const res = await authFetch(
        `/api/api/events/${uid}/background?preset=${encodeURIComponent(presetName)}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error("Failed to set background");
      const data = await res.json();
      setSelectedBg(data.background_image);
      setBgVersion((v) => v + 1);
      showToast("Achtergrond geselecteerd");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    }
  }

  async function uploadCustomBg(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await authFetch(`/api/api/events/${uid}/background`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Upload mislukt");
      const data = await res.json();
      setSelectedBg(data.background_image);
      setBgVersion((v) => v + 1);
      showToast("Achtergrond geüpload");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    }
  }

  async function removeBg() {
    try {
      await authFetch(`/api/api/events/${uid}/background`, {
        method: "DELETE",
      });
      setSelectedBg(null);
      setBgVersion((v) => v + 1);
      showToast("Achtergrond verwijderd");
    } catch {
      showToast("Verwijderen mislukt");
    }
  }

  /* ---- Push to booth ---- */
  async function handlePush() {
    try {
      await handleSave();
      const boothsRes = await authFetch("/api/api/booths");
      if (!boothsRes.ok) throw new Error("Kon booths niet laden");
      const booths = await boothsRes.json();

      let pushed = 0;
      for (const booth of booths) {
        if (booth.event_id) {
          try {
            const res = await authFetch(
              `/api/api/booths/${booth.booth_id}/push-event`,
              { method: "POST" }
            );
            if (res.ok) pushed++;
          } catch {
            /* skip */
          }
        }
      }
      showToast(
        pushed > 0
          ? `Gepusht naar ${pushed} booth(s)`
          : "Geen online booths gevonden"
      );
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    }
  }

  /* ---- Copy to clipboard ---- */
  function copyToClipboard(text: string, label: string) {
    navigator.clipboard.writeText(text);
    showToast(`${label} gekopieerd`);
  }

  /* ---- Preview URL ---- */
  const bgPreviewUrl =
    selectedBg && !isNew
      ? `/api/api/events/${uid}/background?v=${bgVersion}`
      : null;

  /* ================================================================== */
  /*  Render                                                            */
  /* ================================================================== */

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  const tabItems = [
    { key: "general", label: "Algemeen", icon: <Settings /> },
    ...(!isNew
      ? [
          { key: "photocard", label: "Fotokaart", icon: <Palette /> },
          { key: "sharing", label: "QR & Delen", icon: <QrCode /> },
        ]
      : []),
  ];

  return (
    <>
      <PageHeader
        title={isNew ? "Nieuw Event" : form.name || "Event"}
        subtitle={
          isNew
            ? "Vul de gegevens in om een nieuw event aan te maken"
            : `UID: ${uid}`
        }
        actions={
          <div className="flex items-center gap-3">
            {!isNew && (
              <Button
                variant="danger"
                size="sm"
                onClick={() => setShowDelete(true)}
              >
                Verwijderen
              </Button>
            )}
            <Button
              variant="primary"
              icon={<Save />}
              onClick={handleSave}
              disabled={!form.name.trim()}
              loading={saving}
            >
              {isNew ? "Aanmaken" : "Opslaan"}
            </Button>
          </div>
        }
        backHref="/events"
      />

      {/* Tabs */}
      <Tabs
        tabs={tabItems}
        active={tab}
        onChange={(key) => setTab(key as Tab)}
        className="mb-6"
      />

      {/* ============================================================ */}
      {/*  TAB: Algemeen                                                */}
      {/* ============================================================ */}
      {tab === "general" && (
        <div className="max-w-2xl space-y-5">
          <Input
            label="Naam *"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="bv. Bruiloft Jan & Lisa"
            autoFocus={isNew}
          />

          <Textarea
            label="Beschrijving"
            value={form.description}
            onChange={(e) =>
              setForm({ ...form, description: e.target.value })
            }
            rows={3}
            placeholder="Optionele beschrijving..."
          />

          {/* Start date + End date */}
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Startdatum"
              type="datetime-local"
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
              helper="Informatief — de booth werkt ook vóór deze datum"
            />
            <Input
              label="Einddatum"
              type="datetime-local"
              value={form.end_date}
              onChange={(e) =>
                setForm({ ...form, end_date: e.target.value })
              }
              helper="Na deze datum + 24u stopt de booth met uploaden. De galerij blijft bereikbaar."
            />
          </div>

          {/* Active toggle */}
          {!isNew && (
            <Toggle
              checked={form.is_active}
              onChange={(checked) =>
                setForm({ ...form, is_active: checked })
              }
              label="Event is actief"
              className="pt-1"
            />
          )}

          {/* Photo count */}
          {event && (event.photo_count ?? 0) > 0 && (
            <div className="pt-2">
              <Button
                variant="secondary"
                size="sm"
                icon={<Camera />}
                onClick={() => router.push(`/events/${uid}/photos`)}
              >
                {event.photo_count} foto
                {event.photo_count !== 1 ? "'s" : ""} bekijken
              </Button>
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/*  TAB: Fotokaart                                               */}
      {/* ============================================================ */}
      {tab === "photocard" && !isNew && (
        <div className="flex gap-8">
          {/* Left: Settings */}
          <div className="flex-1 max-w-2xl space-y-8">
            {/* Background picker */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-[var(--foreground)]">
                  Achtergrond afbeelding
                </h4>
                {selectedBg && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={removeBg}
                    className="text-[var(--danger)] hover:text-[var(--danger)]"
                  >
                    Verwijder achtergrond
                  </Button>
                )}
              </div>

              <div className="grid grid-cols-5 gap-3">
                {presets.map((preset) => (
                  <button
                    key={preset.name}
                    onClick={() => selectPreset(preset.name)}
                    className={`relative group rounded-xl overflow-hidden border-2 transition-all duration-200 aspect-[2/3] ${
                      selectedBg === `presets/${preset.name}`
                        ? "border-violet-500 ring-2 ring-[var(--accent)]/20"
                        : "border-[var(--card-border)] hover:border-gray-300"
                    }`}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={`/api${preset.url}`}
                      alt={preset.label}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-1.5">
                      <span className="text-[10px] text-[var(--foreground)] font-medium leading-tight block">
                        {preset.label}
                      </span>
                    </div>
                    {selectedBg === `presets/${preset.name}` && (
                      <div className="absolute top-1.5 right-1.5 w-5 h-5 bg-[var(--accent-dark)] rounded-full flex items-center justify-center">
                        <Check className="w-3 h-3 text-[var(--foreground)]" />
                      </div>
                    )}
                  </button>
                ))}

                {/* Upload custom */}
                <label className="relative rounded-xl border-2 border-dashed border-[var(--card-border)] hover:border-gray-300 cursor-pointer transition-all duration-200 aspect-[2/3] flex flex-col items-center justify-center gap-1.5">
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) uploadCustomBg(file);
                    }}
                  />
                  <Plus className="w-6 h-6 text-[var(--muted-light)]" />
                  <span className="text-[10px] text-[var(--muted-light)] font-medium">
                    Upload
                  </span>
                </label>
              </div>
            </div>

            {/* Branding text */}
            <div>
              <h4 className="text-sm font-semibold text-[var(--foreground)] mb-3">
                Tekst op strook
              </h4>
              <div className="space-y-4">
                <Input
                  label="Datum op fotokaart"
                  value={displayDate}
                  onChange={(e) => setDisplayDate(e.target.value)}
                  placeholder="bv. Woensdag 15 April 2026"
                  helper="Deze datum verschijnt op elke fotokaart"
                />

                <Textarea
                  label="Tekst"
                  value={brandingText}
                  onChange={(e) => setBrandingText(e.target.value)}
                  rows={3}
                  placeholder={"**Titel** ✨\n_Subtekst_"}
                  helper="Markdown: **vet**, *cursief*"
                  className="font-mono"
                />

                <div>
                  <label className="text-sm text-[var(--muted)] block mb-1.5">
                    Voorbeeld
                  </label>
                  <div
                    className="bg-white border border-[var(--card-border)] rounded-lg px-4 py-3 text-[var(--foreground)] text-sm"
                    dangerouslySetInnerHTML={{
                      __html: renderSimpleMarkdown(brandingText),
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Push to booth button */}
            <div className="pt-2 border-t border-[var(--card-border)]">
              <Button
                variant="secondary"
                icon={<Send />}
                onClick={handlePush}
              >
                Push naar Booth
              </Button>
              <p className="text-xs text-[var(--muted-light)] mt-2">
                Stuurt de fotokaart instellingen naar alle verbonden booths
              </p>
            </div>
          </div>

          {/* Right: Live preview */}
          <div className="w-[340px] shrink-0">
            <h4 className="text-sm font-semibold text-[var(--muted)] mb-3">
              Preview
            </h4>
            <div className="sticky top-6">
              {/* Layout selector */}
              <div className="flex gap-1 mb-3 bg-gray-50 rounded-lg p-1">
                {(Object.keys(CARD.layouts) as PreviewLayout[]).map((key) => (
                  <button
                    key={key}
                    onClick={() => setPreviewLayout(key)}
                    className={`flex-1 text-[11px] font-medium py-1.5 rounded-md transition-all ${
                      previewLayout === key
                        ? "bg-[var(--accent)] text-[var(--foreground)] shadow-sm"
                        : "text-[var(--muted)] hover:text-[var(--foreground)]"
                    }`}
                  >
                    {CARD.layouts[key].label}
                  </button>
                ))}
              </div>

              <div
                className="relative rounded-xl overflow-hidden border border-[var(--card-border)] shadow-lg"
                style={{ aspectRatio: `${CARD.canvas.width}/${CARD.canvas.height}` }}
              >
                {/* Background */}
                {bgPreviewUrl ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={bgPreviewUrl}
                    alt="Background"
                    className="absolute inset-0 w-full h-full object-cover"
                  />
                ) : (
                  <div className="absolute inset-0 bg-white" />
                )}

                {/* Photo area with slot placeholders */}
                <div
                  className="absolute"
                  style={{
                    left: `${PAD_PCT}%`,
                    right: `${PAD_PCT}%`,
                    top: `${PAD_PCT}%`,
                    bottom: `${CARD.branding.heightPercent + PAD_PCT}%`,
                  }}
                >
                  {CARD.layouts[previewLayout].slots.map((slot, i) => (
                    <div
                      key={i}
                      className="absolute bg-gray-400/30 rounded-md flex items-center justify-center backdrop-blur-sm border border-white/10"
                      style={{
                        left: `${slot.x}%`,
                        top: `${slot.y}%`,
                        width: `${slot.w}%`,
                        height: `${slot.h}%`,
                      }}
                    >
                      <span className="text-[var(--muted)] text-[9px] font-medium flex items-center gap-0.5">
                        <Camera className="w-3 h-3" />
                        {i + 1}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Branding strip — exact match with booth rendering */}
                <div
                  className="absolute inset-x-0 bottom-0 flex flex-col justify-center px-3 py-2"
                  style={{
                    height: `${CARD.branding.heightPercent}%`,
                    backgroundColor: bgPreviewUrl
                      ? "rgba(28, 32, 40, 0.85)"
                      : CARD.branding.colors.background,
                  }}
                >
                  {/* Accent line */}
                  <div
                    className="w-full rounded mb-2"
                    style={{
                      height: "2px",
                      backgroundColor: CARD.branding.colors.accent,
                    }}
                  />
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <div
                        className="text-[8px] leading-tight line-clamp-2"
                        style={{ color: CARD.branding.colors.text }}
                        dangerouslySetInnerHTML={{
                          __html: renderSimpleMarkdown(brandingText),
                        }}
                      />
                    </div>
                    <div className="w-7 h-7 bg-white/20 rounded-md flex items-center justify-center shrink-0">
                      <span className="text-[8px]" style={{ color: CARD.branding.colors.text }}>LOGO</span>
                    </div>
                  </div>
                  {displayDate && (
                    <div
                      className="text-[6px] leading-tight whitespace-nowrap absolute bottom-1.5 left-3"
                      style={{ color: CARD.branding.colors.text, opacity: 0.7 }}
                    >
                      {displayDate}
                    </div>
                  )}
                </div>
              </div>
              <p className="text-[10px] text-[var(--muted-light)] mt-2 text-center">
                10 × 15 cm fotokaart • {CARD.layouts[previewLayout].label}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/*  TAB: QR & Delen                                              */}
      {/* ============================================================ */}
      {tab === "sharing" && !isNew && event && (
        <div className="max-w-2xl">
          <Card padding="lg">
            <div className="flex gap-8 items-start">
              {/* QR Code */}
              <div className="shrink-0">
                <div className="p-4 bg-white rounded-xl shadow-lg">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(`${PUBLIC_BASE}/${event.uid}`)}`}
                    alt={`QR code voor ${event.name}`}
                    width={200}
                    height={200}
                  />
                </div>
              </div>

              {/* Info */}
              <div className="flex-1 space-y-5">
                <div>
                  <h4 className="text-sm font-semibold text-[var(--foreground)] mb-2">
                    Publieke galerij URL
                  </h4>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 bg-gray-50 border border-[var(--card-border)] px-3 py-2 rounded-lg text-sm text-[var(--foreground)] font-mono truncate">
                      {PUBLIC_BASE}/{event.uid}
                    </code>
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Copy />}
                      onClick={() =>
                        copyToClipboard(
                          `${PUBLIC_BASE}/${event.uid}`,
                          "URL"
                        )
                      }
                    >
                      Kopieer
                    </Button>
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-semibold text-[var(--foreground)] mb-2">
                    Event UID
                  </h4>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 bg-gray-50 border border-[var(--card-border)] px-3 py-2 rounded-lg text-sm text-[var(--foreground)] font-mono">
                      {event.uid}
                    </code>
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Copy />}
                      onClick={() =>
                        copyToClipboard(event.uid, "UID")
                      }
                    >
                      Kopieer
                    </Button>
                  </div>
                </div>

                <div>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<ExternalLink />}
                    onClick={() =>
                      window.open(`${PUBLIC_BASE}/${event.uid}`, "_blank")
                    }
                  >
                    Open galerij in nieuw tabblad
                  </Button>
                </div>

                <p className="text-xs text-[var(--muted-light)] pt-2">
                  Gasten kunnen deze QR-code scannen om de publieke foto
                  galerij van het event te bekijken.
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* ---- Delete Confirmation ---- */}
      <Modal
        open={showDelete}
        onClose={() => setShowDelete(false)}
        title="Event Verwijderen"
        maxWidth="sm"
        actions={
          <>
            <Button variant="ghost" onClick={() => setShowDelete(false)}>
              Annuleren
            </Button>
            <Button
              variant="danger"
              onClick={handleDelete}
              loading={deleting}
              icon={<Trash2 />}
            >
              Verwijderen
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--muted)]">
          Weet je zeker dat je{" "}
          <strong className="text-[var(--foreground)]">{form.name}</strong> wilt
          verwijderen? Dit kan niet ongedaan worden.
        </p>
      </Modal>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast}
          onDismiss={() => setToast("")}
        />
      )}
    </>
  );
}
