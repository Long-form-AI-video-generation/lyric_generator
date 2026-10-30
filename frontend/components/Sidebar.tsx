"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { LogOut, Send, Shield, UserPlus, X } from "lucide-react";
import { useAuthStore } from "@/store/useAuthStore";
import { createInviteApi } from "@/lib/api";

type SidebarProps = {
  isOpen: boolean;
  onClose: () => void;
};

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteCredits, setInviteCredits] = useState(3);
  const [loading, setLoading] = useState(false);
  const [successEmail, setSuccessEmail] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function handleSendInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail) return;
    setLoading(true);
    setError("");
    setSuccessEmail(null);

    try {
      const res = await createInviteApi(inviteEmail, inviteCredits);
      setSuccessEmail(res.email);
      setInviteEmail("");
    } catch (err: any) {
      setError(err.message || "Failed to create invite.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
          />

          {/* Drawer */}
          <motion.aside
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 250 }}
            className="fixed inset-y-0 left-0 z-50 w-80 sm:w-96 bg-zinc-950 border-r border-white/10 p-6 flex flex-col justify-between shadow-2xl overflow-y-auto"
          >
            <div className="space-y-6">
              {/* Header */}
              <div className="flex items-center justify-between pb-4 border-b border-white/10">
                <div className="flex items-center gap-3">
                  <div className="grid h-9 w-9 place-items-center rounded-lg border border-violet-500/40 bg-violet-500/15 font-display text-sm font-black text-white">
                    LV
                  </div>
                  <div>
                    <h2 className="font-display font-bold text-white text-base">LyricVid</h2>
                    <p className="text-xs text-zinc-400">Workspace Menu</p>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="rounded-lg p-1.5 text-zinc-400 hover:text-white hover:bg-white/5 transition"
                  aria-label="Close menu"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* User Profile Card */}
              {user && (
                <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-zinc-400">Signed In</span>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                        user.role === "admin"
                          ? "bg-violet-500/20 text-violet-300 border border-violet-500/30"
                          : "bg-zinc-800 text-zinc-300"
                      }`}
                    >
                      {user.role === "admin" && <Shield className="h-3 w-3" />}
                      {user.role}
                    </span>
                  </div>
                  <div className="text-sm font-semibold text-white truncate">{user.email}</div>
                  <div className="pt-2 border-t border-white/5 flex items-center justify-between text-xs">
                    <span className="text-zinc-400">Available Credits</span>
                    <span className="font-semibold text-violet-400">⚡ {user.credits_remaining} credits</span>
                  </div>
                </div>
              )}

              {/* Admin Invite Section */}
              {user?.role === "admin" && (
                <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-4 space-y-3">
                  <div className="flex items-center gap-2 text-violet-300">
                    <UserPlus className="h-4 w-4" />
                    <h3 className="text-xs font-bold uppercase tracking-wider">Invite Beta Tester</h3>
                  </div>

                  {error && (
                    <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-2 text-xs text-red-400">
                      {error}
                    </div>
                  )}

                  <form onSubmit={handleSendInvite} className="space-y-3">
                    <div>
                      <label className="block text-[11px] font-medium text-zinc-400 mb-1">
                        Invitee Email
                      </label>
                      <input
                        type="email"
                        required
                        value={inviteEmail}
                        onChange={(e) => setInviteEmail(e.target.value)}
                        placeholder="artist@label.com"
                        className="w-full rounded-lg border border-white/10 bg-zinc-900 px-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:border-violet-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-[11px] font-medium text-zinc-400 mb-1">
                        Credit Allowance
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={100}
                        value={inviteCredits}
                        onChange={(e) => setInviteCredits(Number(e.target.value))}
                        className="w-full rounded-lg border border-white/10 bg-zinc-900 px-3 py-1.5 text-xs text-white focus:border-violet-500 focus:outline-none"
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-violet-600 px-3 py-2 text-xs font-semibold text-white hover:bg-violet-500 disabled:opacity-50 transition"
                    >
                      <Send className="h-3.5 w-3.5" />
                      {loading ? "Sending..." : "Send Invitation"}
                    </button>
                  </form>

                  {successEmail && (
                    <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-3 text-xs text-emerald-400">
                      ✓ Invitation email dispatched successfully to{" "}
                      <span className="font-semibold text-white">{successEmail}</span>!
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Bottom Actions */}
            <div className="pt-6 border-t border-white/10">
              <button
                onClick={() => {
                  logout();
                  router.push("/login");
                }}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 py-2.5 text-xs font-semibold text-red-400 hover:text-red-300 transition"
              >
                <LogOut className="h-4 w-4" />
                Sign Out
              </button>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
