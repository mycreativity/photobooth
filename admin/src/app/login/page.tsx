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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950">
      <div className="w-full max-w-md p-8">
        {/* Logo / Brand */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-violet-600/20 mb-4">
            <span className="text-3xl">📸</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Photobooth Admin</h1>
          <p className="text-gray-400 mt-1 text-sm">Log in met je email</p>
        </div>

        {/* Card */}
        <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl p-6 shadow-2xl">
          {step === "email" ? (
            <form onSubmit={requestOTP} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1.5">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jouw@email.nl"
                  className="w-full px-4 py-3 bg-gray-900/50 border border-gray-600/50 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-200 hover:shadow-lg hover:shadow-violet-500/25"
              >
                {loading ? "Verzenden..." : "Stuur login code →"}
              </button>
            </form>
          ) : (
            <form onSubmit={verifyOTP} className="space-y-4">
              <p className="text-gray-300 text-sm">
                We hebben een code gestuurd naar{" "}
                <span className="text-white font-medium">{email}</span>
              </p>
              <div>
                <label htmlFor="code" className="block text-sm font-medium text-gray-300 mb-1.5">
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
                  className="w-full px-4 py-3 bg-gray-900/50 border border-gray-600/50 rounded-xl text-white text-center text-2xl font-mono tracking-[0.5em] placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition"
                  autoFocus
                />
              </div>
              <button
                type="submit"
                disabled={loading || code.length !== 6}
                className="w-full py-3 px-4 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-200 hover:shadow-lg hover:shadow-violet-500/25"
              >
                {loading ? "Verifiëren..." : "Inloggen"}
              </button>
              <button
                type="button"
                onClick={() => { setStep("email"); setCode(""); setError(""); }}
                className="w-full py-2 text-gray-400 hover:text-white text-sm transition"
              >
                ← Ander email adres
              </button>
            </form>
          )}

          {error && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}
        </div>

        <p className="text-center text-gray-600 text-xs mt-6">
          Check ook je spam als je de code niet ziet
        </p>
      </div>
    </div>
  );
}
