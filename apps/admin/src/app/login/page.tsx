"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { setTokens, isLoggedIn } from "@/lib/auth";

type Step = "email" | "otp";

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isLoggedIn()) router.replace("/");
  }, [router]);

  async function requestOTP(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/auth/otp/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to send OTP");
      }

      setStep("otp");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function verifyOTP(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/auth/otp/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Invalid code");
      }

      const data = await res.json();
      setTokens(data.access_token, data.refresh_token);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
      <div className="w-full max-w-md p-8">
        {/* Logo / Brand */}
        <div className="text-center mb-10">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/loomo-logo-dark.png" alt="LOOMO" className="h-14 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-[var(--foreground)]">Admin Panel</h1>
          <p className="text-[var(--muted)] mt-1 text-sm">Log in met je email</p>
        </div>

        {/* Card */}
        <div className="bg-white border border-[var(--card-border)] rounded-2xl p-6 shadow-sm">
          {step === "email" ? (
            <form onSubmit={requestOTP} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-[var(--foreground)] mb-1.5">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jouw@email.nl"
                  className="w-full px-4 py-3 bg-white border border-[var(--input-border)] rounded-xl text-[var(--foreground)] placeholder-[var(--muted-light)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20 focus:border-[var(--accent)] transition"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 bg-[var(--accent)] hover:bg-[var(--accent-dark)] disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-200 hover:shadow-lg hover:shadow-[var(--accent)]/20"
              >
                {loading ? "Verzenden..." : "Stuur login code →"}
              </button>
            </form>
          ) : (
            <form onSubmit={verifyOTP} className="space-y-4">
              <p className="text-[var(--muted)] text-sm">
                We hebben een code gestuurd naar{" "}
                <span className="text-[var(--foreground)] font-medium">{email}</span>
              </p>
              <div>
                <label htmlFor="code" className="block text-sm font-medium text-[var(--foreground)] mb-1.5">
                  Login code
                </label>
                <input
                  id="code"
                  type="text"
                  required
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="000000"
                  className="w-full px-4 py-3 bg-white border border-[var(--input-border)] rounded-xl text-[var(--foreground)] text-center text-2xl font-mono tracking-[0.5em] placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/20 focus:border-[var(--accent)] transition"
                  autoFocus
                />
              </div>
              <button
                type="submit"
                disabled={loading || code.length !== 6}
                className="w-full py-3 px-4 bg-[var(--accent)] hover:bg-[var(--accent-dark)] disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-200 hover:shadow-lg hover:shadow-[var(--accent)]/20"
              >
                {loading ? "Verifiëren..." : "Inloggen"}
              </button>
              <button
                type="button"
                onClick={() => { setStep("email"); setCode(""); setError(""); }}
                className="w-full py-2 text-[var(--muted)] hover:text-[var(--foreground)] text-sm transition"
              >
                ← Ander email adres
              </button>
            </form>
          )}

          {error && (
            <div className="mt-4 p-3 bg-[var(--danger-light)] border border-red-200 rounded-xl">
              <p className="text-[var(--danger)] text-sm">{error}</p>
            </div>
          )}
        </div>

        <p className="text-center text-[var(--muted-light)] text-xs mt-6">
          Check ook je spam als je de code niet ziet
        </p>
      </div>
    </div>
  );
}
