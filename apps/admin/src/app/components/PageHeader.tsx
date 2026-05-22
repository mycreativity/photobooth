/**
 * Consistent page header used across all admin pages.
 */
import { ChevronLeft } from "lucide-react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  backHref?: string;
  actions?: React.ReactNode;
  badge?: React.ReactNode;
}

export default function PageHeader({
  title,
  subtitle,
  backHref,
  actions,
  badge,
}: PageHeaderProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-8">
      <div className="flex items-center gap-3">
        {backHref && (
          <a
            href={backHref}
            className="p-1.5 -ml-1.5 text-[var(--muted-light)] hover:text-[var(--foreground)] hover:bg-gray-100 rounded-lg transition"
          >
            <ChevronLeft className="w-5 h-5" />
          </a>
        )}
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl sm:text-2xl font-bold text-[var(--foreground)]">{title}</h1>
            {badge}
          </div>
          {subtitle && (
            <p className="text-[var(--muted)] text-sm mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  );
}
