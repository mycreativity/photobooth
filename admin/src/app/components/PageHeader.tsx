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
    <div className="flex items-start justify-between mb-8">
      <div className="flex items-center gap-3">
        {backHref && (
          <a
            href={backHref}
            className="p-1.5 -ml-1.5 text-gray-400 hover:text-white hover:bg-gray-800/50 rounded-lg transition"
          >
            <ChevronLeft className="w-5 h-5" />
          </a>
        )}
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">{title}</h1>
            {badge}
          </div>
          {subtitle && (
            <p className="text-gray-400 text-sm mt-1">{subtitle}</p>
          )}
        </div>
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  );
}
