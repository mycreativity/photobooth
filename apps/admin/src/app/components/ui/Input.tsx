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
        <label className="text-sm font-medium text-gray-300 block mb-1.5">
          {label}
        </label>
      )}
      {children}
      {(helper || error) && (
        <p className={`text-xs mt-1 ${error ? "text-red-400" : "text-gray-500"}`}>
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
  "w-full bg-gray-800/50 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/20 transition";

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
        className={`${inputBase} ${error ? "border-red-500/50" : ""} ${className}`}
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
        className={`${inputBase} resize-none ${error ? "border-red-500/50" : ""} ${className}`}
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
        className={`${inputBase} appearance-none cursor-pointer ${error ? "border-red-500/50" : ""} ${className}`}
        {...props}
      >
        {children}
      </select>
    </FieldWrapper>
  );
}
