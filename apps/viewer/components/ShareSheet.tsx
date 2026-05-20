"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Download, Link2, Mail, Share2 } from "lucide-react";
import { downloadPhoto, sharePhoto, copyToClipboard, getMailtoLink, hasNativeShare } from "@/lib/share";
import styles from "./ShareSheet.module.css";

interface ShareSheetProps {
  photo: {
    id: string;
    variant: string;
    url: string;
    seq: number;
  };
  eventName: string;
  open: boolean;
  onClose: () => void;
}

export function ShareSheet({ photo, eventName, open, onClose }: ShareSheetProps) {
  const [toast, setToast] = useState<string | null>(null);
  const isLayout = photo.variant === "print";
  const photoUrl = `${process.env.NEXT_PUBLIC_API_URL || "/api"}${photo.url}`;
  const filename = isLayout ? "photobooth_strip.jpg" : `photobooth_${photo.seq}.jpg`;
  const title = isLayout ? `Photobooth strip — ${eventName}` : `Photobooth foto — ${eventName}`;

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 2000);
  }

  async function handleNativeShare() {
    const result = await sharePhoto(photoUrl, title, window.location.href);
    if (result === "shared" || result === "link-shared") {
      onClose();
    }
  }

  async function handleDownload() {
    await downloadPhoto(photoUrl, filename);
    showToast("Gedownload");
  }

  async function handleCopyLink() {
    const ok = await copyToClipboard(window.location.href);
    if (ok) showToast("Link gekopieerd");
  }

  function handleEmail() {
    const body = `Bekijk mijn photobooth foto's: ${window.location.href}`;
    window.location.href = getMailtoLink(title, body);
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className={styles.backdrop}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Sheet */}
          <motion.div
            className={styles.sheet}
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
          >
            <div className={styles.handle} />

            <h2 className={styles.title}>
              {isLayout ? "Deel je strip" : "Deel je foto"}
            </h2>

            <div className={styles.options}>
              {hasNativeShare() && (
                <button className={styles.option} onClick={handleNativeShare}>
                  <div className={styles.iconWrap}>
                    <Share2 size={22} />
                  </div>
                  <span>Deel</span>
                </button>
              )}

              <button className={styles.option} onClick={handleDownload}>
                <div className={styles.iconWrap}>
                  <Download size={22} />
                </div>
                <span>Download</span>
              </button>

              <button className={styles.option} onClick={handleCopyLink}>
                <div className={styles.iconWrap}>
                  <Link2 size={22} />
                </div>
                <span>Kopieer link</span>
              </button>

              <button className={styles.option} onClick={handleEmail}>
                <div className={styles.iconWrap}>
                  <Mail size={22} />
                </div>
                <span>Email</span>
              </button>
            </div>

            <button className={styles.closeBtn} onClick={onClose}>
              <X size={20} />
              <span>Sluiten</span>
            </button>

            {/* Toast */}
            <AnimatePresence>
              {toast && (
                <motion.div
                  className={styles.toast}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                >
                  {toast}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
