"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { verifyInviteApi, acceptInviteApi, getProfileApi } from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";

function AcceptInviteContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [verifying, setVerifying] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  useEffect(() => {
    if (!token) {
      setError("No invite token provided in the link.");
      setVerifying(false);
      return;
    }

    verifyInviteApi(token)
      .then((res) => {
        setEmail(res.email);
        setVerifying(false);
      })
      .catch((err) => {
        setError(err.message || "This invite link is invalid or has expired.");
        setVerifying(false);
      });
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const tokenRes = await acceptInviteApi(token, password);
      localStorage.setItem(
        "lyricvid-auth",
        JSON.stringify({ state: { token: tokenRes.access_token } })
      );
      const profile = await getProfileApi();
      setAuth(tokenRes.access_token, profile);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Could not accept invite.");
    } finally {
      setLoading(false);
    }
  }

  if (verifying) {
    return (
      <div className="flex min-h-screen items-center justify-center text-white">
        Verifying invite link...
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-surface/60 p-8 backdrop-blur-xl shadow-2xl">
        <h1 className="text-2xl font-bold text-white mb-2">Join LyricVid Beta</h1>
        <p className="text-sm text-text-muted mb-6">
          Invited email: <span className="font-semibold text-white">{email}</span>
        </p>

        {error && (
          <div className="mb-4 rounded-lg bg-red-500/10 border border-red-500/30 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {!error && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Create a Password (min 8 characters)
              </label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-white placeholder-white/30 focus:border-primary focus:outline-none"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 rounded-xl bg-primary py-2.5 font-medium text-white hover:bg-primary-hover disabled:opacity-50 transition"
            >
              {loading ? "Activating account..." : "Accept Invite & Get Started"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-white">Loading...</div>}>
      <AcceptInviteContent />
    </Suspense>
  );
}
