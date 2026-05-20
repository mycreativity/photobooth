"use client";

import { Download, Share2, ChevronLeft, ChevronRight } from "lucide-react";
import { downloadPhoto } from "@/lib/share";
import styles from "./ActionPanel.module.css";

interface ActionPanelProps {
  photo: {
    id: string;
    variant: string;
    url: string;
    seq: number;
  };
  onShare: () => void;
  onPrev?: () => void;
  onNext?: () => void;
}

export function ActionPanel({ photo, onShare, onPrev, onNext }: ActionPanelProps) {
  const isLayout = photo.variant === "print";

  function handleDownload() {
    const photoUrl = `${process.env.NEXT_PUBLIC_API_URL || "/api"}${photo.url}`;
    const filename = isLayout ? "photobooth_strip.jpg" : `photobooth_${photo.seq}.jpg`;
    downloadPhoto(photoUrl, filename);
  }

  return (
    <div className={styles.panel}>
      <div className={styles.inner}>
        {/* Navigation */}
        <button
          className={`${styles.navBtn} ${!onPrev ? styles.disabled : ""}`}
          onClick={onPrev}
          disabled={!onPrev}
          aria-label="Vorige foto"
        >
          <ChevronLeft size={20} />
        </button>

        {/* Actions */}
        <div className={styles.actions}>
          <button className={styles.actionBtn} onClick={onShare}>
            <Share2 size={20} />
            <span>Deel</span>
          </button>

          <button className={styles.actionBtn} onClick={handleDownload}>
            <Download size={20} />
            <span>Download</span>
          </button>
        </div>

        {/* Navigation */}
        <button
          className={`${styles.navBtn} ${!onNext ? styles.disabled : ""}`}
          onClick={onNext}
          disabled={!onNext}
          aria-label="Volgende foto"
        >
          <ChevronRight size={20} />
        </button>
      </div>
    </div>
  );
}
