import type { PreviewLayout } from "./_types";

/* ------------------------------------------------------------------ */
/*  Card layout constants (from shared/card_layout.json)               */
/* ------------------------------------------------------------------ */

export const CARD = {
  canvas: { width: 1200, height: 1800 },
  padding: 20,
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

// Derived constants
export const PAD_PCT = (CARD.padding / CARD.canvas.height) * 100;

/* ------------------------------------------------------------------ */
/*  Simple markdown → HTML                                             */
/* ------------------------------------------------------------------ */

export function renderSimpleMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/__(.+?)__/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/_(.+?)_/g, "<em>$1</em>")
    .replace(/\n/g, "<br />");
}

/* ------------------------------------------------------------------ */
/*  Public viewer base URL                                             */
/* ------------------------------------------------------------------ */

export const PUBLIC_BASE = "https://booth.mycreativity.nl/e";
