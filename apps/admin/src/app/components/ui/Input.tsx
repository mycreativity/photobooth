import { type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes, type ReactNode } from "react";

/* ------------------------------------------------------------------ */
/*  Shared wrapper                                                     */
/* ------------------------------------------------------------------ */

interface FieldWrapperProps {
  label?: string;
  helper?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}

function FieldWrapper({ label, helper, error, children, className = "" }: FieldWrapperProps) {
  return (
    <div className={className}>
      {label && (
        <label className="text-sm font-medium text-[var(--foreground)] block mb-1.5">
          {label}
        </label>
      )}
      {children}
      {(helper || error) && (
        <p className={`text-xs mt-1 ${error ? "text-[var(--danger)]" : "text-[var(--muted-light)]"}`}>
          {error || helper}
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Input                                                              */
/* ------------------------------------------------------------------ */

const inputBase =
  "w-full bg-white border border-[var(--input-border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-light)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/15 transition";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helper?: string;
  error?: string;
  wrapperClassName?: string;
}

export function Input({ label, helper, error, wrapperClassName, className = "", ...props }: InputProps) {
  return (
    <FieldWrapper label={label} helper={helper} error={error} className={wrapperClassName}>
      <input
        className={`${inputBase} ${error ? "border-[var(--danger)]" : ""} ${className}`}
        {...props}
      />
    </FieldWrapper>
  );
}

/* ------------------------------------------------------------------ */
/*  Textarea                                                           */
/* ------------------------------------------------------------------ */

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  helper?: string;
  error?: string;
  wrapperClassName?: string;
}

export function Textarea({ label, helper, error, wrapperClassName, className = "", ...props }: TextareaProps) {
  return (
    <FieldWrapper label={label} helper={helper} error={error} className={wrapperClassName}>
      <textarea
        className={`${inputBase} resize-none ${error ? "border-[var(--danger)]" : ""} ${className}`}
        {...props}
      />
    </FieldWrapper>
  );
}

/* ------------------------------------------------------------------ */
/*  Select                                                             */
/* ------------------------------------------------------------------ */

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  helper?: string;
  error?: string;
  wrapperClassName?: string;
  children: ReactNode;
}

export function Select({ label, helper, error, wrapperClassName, className = "", children, ...props }: SelectProps) {
  return (
    <FieldWrapper label={label} helper={helper} error={error} className={wrapperClassName}>
      <select
        className={`${inputBase} appearance-none cursor-pointer ${error ? "border-[var(--danger)]" : ""} ${className}`}
        {...props}
      >
        {children}
      </select>
    </FieldWrapper>
  );
}
