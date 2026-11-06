"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { loginApi, getProfileApi } from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const tokenRes = await loginApi(email, password);
      localStorage.setItem(
        "lyricvid-auth",
        JSON.stringify({ state: { token: tokenRes.access_token } })
      );
      const profile = await getProfileApi();
      setAuth(tokenRes.access_token, profile);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Failed to sign in.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-surface/60 p-8 backdrop-blur-xl shadow-2xl">
        <h1 className="text-2xl font-bold text-white mb-2 tracking-tight">LyricVid Sign In</h1>
        <p className="text-sm text-text-muted mb-6">
          Private Beta. Sign-in is available for invited users only.
        </p>

        {error && (
          <div className="mb-4 rounded-lg bg-red-500/10 border border-red-500/30 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-white placeholder-white/30 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="you@artist.com"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-white placeholder-white/30 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 rounded-xl bg-primary py-2.5 font-medium text-white shadow-lg shadow-primary/20 hover:bg-primary-hover disabled:opacity-50 transition"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
