"use client";

import { useEffect, useState } from "react";
import { CheckCircle, AlertCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface ToastProps {
  message: string;
  type?: ToastType;
  duration?: number;
  onDismiss: () => void;
}

const icons: Record<ToastType, typeof CheckCircle> = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
};

const typeStyles: Record<ToastType, string> = {
  success: "border-emerald-200 bg-white",
  error: "border-red-200 bg-white",
  info: "border-gray-200 bg-white",
};

const iconColors: Record<ToastType, string> = {
  success: "text-emerald-500",
  error: "text-red-500",
  info: "text-[var(--muted)]",
};

export default function Toast({
  message,
  type = "info",
  duration = 2500,
  onDismiss,
}: ToastProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(onDismiss, 200);
    }, duration);
    return () => clearTimeout(timer);
  }, [duration, onDismiss]);

  const Icon = icons[type];

  return (
    <div
      className={`
        fixed bottom-6 left-1/2 -translate-x-1/2 z-50
        flex items-center gap-2.5
        ${typeStyles[type]} border
        text-[var(--foreground)] text-sm px-4 py-2.5 rounded-lg shadow-lg
        transition-all duration-200
        ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"}
      `}
    >
      <Icon className={`w-4 h-4 shrink-0 ${iconColors[type]}`} />
      <span>{message}</span>
      <button
        onClick={() => {
          setVisible(false);
          setTimeout(onDismiss, 200);
        }}
        className="p-0.5 text-[var(--muted-light)] hover:text-[var(--foreground)] transition shrink-0"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
