import { type ReactNode } from "react";

interface Tab {
  key: string;
  label: string;
  icon?: ReactNode;
}

interface TabsProps {
  tabs: Tab[];
  active: string;
  onChange: (key: string) => void;
  className?: string;
}

export default function Tabs({ tabs, active, onChange, className = "" }: TabsProps) {
  return (
    <div className={`flex border-b border-[var(--card-border)] ${className}`}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`
            inline-flex items-center gap-2 px-4 py-3
            text-sm font-medium border-b-2 transition-colors
            ${
              active === tab.key
                ? "text-[var(--accent-dark)] border-[var(--accent)]"
                : "text-[var(--muted)] border-transparent hover:text-[var(--foreground)] hover:border-gray-300"
            }
          `}
        >
          {tab.icon && (
            <span className="shrink-0 [&>svg]:w-4 [&>svg]:h-4">{tab.icon}</span>
          )}
          {tab.label}
        </button>
      ))}
    </div>
  );
}
