"use client";

import { useState } from "react";
import { Input, Textarea, Button } from "@/app/components/ui";
import { Check, Plus, Camera, Send } from "lucide-react";
import { CARD, PAD_PCT, renderSimpleMarkdown } from "./_helpers";
import type { PresetBackground, PreviewLayout } from "./_types";

interface PhotoCardTabProps {
  uid: string;
  presets: PresetBackground[];
  selectedBg: string | null;
  brandingText: string;
  setBrandingText: (text: string) => void;
  displayDate: string;
  setDisplayDate: (date: string) => void;
  bgVersion: number;
  onSelectPreset: (name: string) => void;
  onUploadBg: (file: File) => void;
  onRemoveBg: () => void;
  onPush: () => void;
}

export default function PhotoCardTab({
  uid,
  presets,
  selectedBg,
  brandingText,
  setBrandingText,
  displayDate,
  setDisplayDate,
  bgVersion,
  onSelectPreset,
  onUploadBg,
  onRemoveBg,
  onPush,
}: PhotoCardTabProps) {
  const [previewLayout, setPreviewLayout] = useState<PreviewLayout>("single");

  const bgPreviewUrl = selectedBg
    ? `/api/api/events/${uid}/background?v=${bgVersion}`
    : null;

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Left: Settings */}
      <div className="w-full lg:flex-1 lg:max-w-2xl space-y-8">
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
                onClick={onRemoveBg}
                className="text-[var(--danger)] hover:text-[var(--danger)]"
              >
                Verwijder
              </Button>
            )}
          </div>

          <div className="grid grid-cols-4 sm:grid-cols-5 gap-3">
            {presets.map((preset) => (
              <button
                key={preset.name}
                onClick={() => onSelectPreset(preset.name)}
                className={`relative group rounded-xl overflow-hidden border-2 transition-all duration-200 aspect-[2/3] ${
                  selectedBg === `presets/${preset.name}`
                    ? "border-[var(--accent)] ring-2 ring-[var(--accent)]/20"
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
                  <span className="text-[10px] text-white font-medium leading-tight block">
                    {preset.label}
                  </span>
                </div>
                {selectedBg === `presets/${preset.name}` && (
                  <div className="absolute top-1.5 right-1.5 w-5 h-5 bg-[var(--accent)] rounded-full flex items-center justify-center">
                    <Check className="w-3 h-3 text-white" />
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
                  if (file) onUploadBg(file);
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
          <Button variant="secondary" icon={<Send />} onClick={onPush}>
            Push naar Booth
          </Button>
          <p className="text-xs text-[var(--muted-light)] mt-2">
            Stuurt de fotokaart instellingen naar alle verbonden booths
          </p>
        </div>
      </div>

      {/* Right: Live preview */}
      <div className="w-full lg:w-[340px] lg:shrink-0">
        <h4 className="text-sm font-semibold text-[var(--muted)] mb-3">
          Preview
        </h4>
        <div className="lg:sticky lg:top-6">
          {/* Layout selector */}
          <div className="flex gap-1 mb-3 bg-gray-50 rounded-lg p-1">
            {(Object.keys(CARD.layouts) as PreviewLayout[]).map((key) => (
              <button
                key={key}
                onClick={() => setPreviewLayout(key)}
                className={`flex-1 text-[11px] font-medium py-1.5 rounded-md transition-all ${
                  previewLayout === key
                    ? "bg-[var(--accent)] text-white shadow-sm"
                    : "text-[var(--muted)] hover:text-[var(--foreground)]"
                }`}
              >
                {CARD.layouts[key].label}
              </button>
            ))}
          </div>

          <div
            className="relative rounded-xl overflow-hidden border border-[var(--card-border)] shadow-lg"
            style={{
              aspectRatio: `${CARD.canvas.width}/${CARD.canvas.height}`,
            }}
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
              <div className="absolute inset-0 bg-gray-100" />
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

            {/* Branding strip */}
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
                  <span
                    className="text-[8px]"
                    style={{ color: CARD.branding.colors.text }}
                  >
                    LOGO
                  </span>
                </div>
              </div>
              {displayDate && (
                <div
                  className="text-[6px] leading-tight whitespace-nowrap absolute bottom-1.5 left-3"
                  style={{
                    color: CARD.branding.colors.text,
                    opacity: 0.7,
                  }}
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
  );
}
