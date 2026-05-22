import { type ReactNode } from "react";

type BadgeVariant = "success" | "warning" | "danger" | "neutral" | "info";

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  dot?: boolean;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  success: "bg-[var(--success-light)] text-emerald-700 border-emerald-200",
  warning: "bg-[var(--warning-light)] text-amber-700 border-amber-200",
  danger: "bg-[var(--danger-light)] text-red-700 border-red-200",
  neutral: "bg-gray-100 text-gray-600 border-gray-200",
  info: "bg-[var(--info-light)] text-blue-700 border-blue-200",
};

const dotColors: Record<BadgeVariant, string> = {
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
  neutral: "bg-gray-400",
  info: "bg-blue-500",
};

export default function Badge({
  variant = "neutral",
  children,
  dot = false,
  className = "",
}: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1.5 px-2 py-0.5
        text-xs font-medium rounded-full border
        ${variantStyles[variant]}
        ${className}
      `}
    >
      {dot && (
        <span className={`w-1.5 h-1.5 rounded-full ${dotColors[variant]}`} />
      )}
      {children}
    </span>
  );
}
