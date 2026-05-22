import { type ReactNode } from "react";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
  maxWidth?: "sm" | "md" | "lg";
}

const widths = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
};

export default function Modal({
  open,
  onClose,
  title,
  description,
  children,
  actions,
  maxWidth = "md",
}: ModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4">
      <div
        className={`bg-white border border-[var(--card-border)] rounded-xl w-full ${widths[maxWidth]} shadow-xl`}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-5 pb-4">
          <div>
            <h3 className="text-base font-semibold text-[var(--foreground)]">{title}</h3>
            {description && (
              <p className="text-sm text-[var(--muted)] mt-0.5">{description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 text-[var(--muted-light)] hover:text-[var(--foreground)] hover:bg-gray-100 rounded-lg transition -mt-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 pb-4">{children}</div>

        {/* Actions */}
        {actions && (
          <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-[var(--card-border)]">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
