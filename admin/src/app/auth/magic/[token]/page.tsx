"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { setTokens } from "@/lib/auth";

export default function MagicLinkPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function verify() {
      try {
        const { token } = await params;
        const res = await fetch(`/api/auth/otp/magic/${token}`);

        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || "Invalid magic link");
        }

        const data = await res.json();
        setTokens(data.access_token, data.refresh_token);
        router.replace("/");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Verification failed");
        setLoading(false);
      }
    }
    verify();
  }, [params, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950">
      <div className="text-center">
        {loading ? (
          <>
            <div className="w-12 h-12 border-4 border-violet-500/30 border-t-violet-500 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-300">Inloggen...</p>
          </>
        ) : (
          <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl p-8 max-w-sm">
            <p className="text-red-400 mb-4">{error}</p>
            <button
              onClick={() => router.push("/login")}
              className="px-6 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl transition"
            >
              Opnieuw inloggen
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
