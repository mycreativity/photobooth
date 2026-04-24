interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  className?: string;
}

export default function Toggle({ checked, onChange, label, className = "" }: ToggleProps) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`
          relative inline-flex h-5 w-9 shrink-0 cursor-pointer
          rounded-full border-2 border-transparent transition-colors
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500
          ${checked ? "bg-violet-600" : "bg-gray-700"}
        `}
      >
        <span
          className={`
            pointer-events-none inline-block h-4 w-4 transform rounded-full
            bg-white shadow-sm transition-transform
            ${checked ? "translate-x-4" : "translate-x-0"}
          `}
        />
      </button>
      {label && <span className="text-sm text-gray-300">{label}</span>}
    </div>
  );
}
