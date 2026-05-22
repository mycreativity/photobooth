import { type ReactNode } from "react";
import Button from "./Button";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="text-center py-16">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gray-100 mb-4 text-[var(--muted-light)] [&>svg]:w-7 [&>svg]:h-7">
        {icon}
      </div>
      <h3 className="text-base font-semibold text-[var(--foreground)] mb-1">{title}</h3>
      {description && (
        <p className="text-[var(--muted)] text-sm max-w-sm mx-auto mb-5">
          {description}
        </p>
      )}
      {action && (
        <Button variant="primary" size="md" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
