"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  FolderOpen,
  Mail,
  Plus,
  RefreshCw,
  Send,
  Shield,
  ShieldAlert,
  Sparkles,
  UserCheck,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";
import { useAuthStore } from "@/store/useAuthStore";
import {
  activateUserApi,
  createInviteApi,
  fetchAdminInvitesApi,
  fetchAdminUsersApi,
  revokeUserApi,
  updateUserCreditsApi,
} from "@/lib/api";
import type { AdminInviteItem, AdminUserItem } from "@/lib/types";

export default function AdminUsersPage() {
  const router = useRouter();
  const { user, token } = useAuthStore();

  const [activeTab, setActiveTab] = useState<"users" | "invites">("users");
  const [usersList, setUsersList] = useState<AdminUserItem[]>([]);
  const [invitesList, setInvitesList] = useState<AdminInviteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");

  // Quick invite modal/form state
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteCredits, setInviteCredits] = useState(3);
  const [inviteLoading, setInviteLoading] = useState(false);

  // Credit adjustment modal state
  const [adjustingUser, setAdjustingUser] = useState<AdminUserItem | null>(null);
  const [creditAdjustment, setCreditAdjustment] = useState<number>(5);
  const [creditUpdating, setCreditUpdating] = useState(false);

  useEffect(() => {
    if (!token) {
      router.push("/login");
      return;
    }
    if (user && user.role !== "admin") {
      router.push("/");
      return;
    }

    loadData();
  }, [token, user, router]);

  async function loadData() {
    try {
      setLoading(true);
      setError("");
      const [uData, iData] = await Promise.all([
        fetchAdminUsersApi(),
        fetchAdminInvitesApi(),
      ]);
      setUsersList(uData);
      setInvitesList(iData);
    } catch (err: any) {
      setError(err.message || "Failed to load admin data.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSendInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail) return;
    try {
      setInviteLoading(true);
      setError("");
      setActionSuccess("");
      await createInviteApi(inviteEmail, inviteCredits);
      setActionSuccess(`Invitation sent successfully to ${inviteEmail}`);
      setInviteEmail("");
      // reload invites
      const iData = await fetchAdminInvitesApi();
      setInvitesList(iData);
    } catch (err: any) {
      setError(err.message || "Failed to send invitation.");
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleAdjustCredits(e: React.FormEvent) {
    e.preventDefault();
    if (!adjustingUser) return;
    try {
      setCreditUpdating(true);
      setError("");
      setActionSuccess("");
      const res = await updateUserCreditsApi(adjustingUser.id, undefined, creditAdjustment);
      setActionSuccess(`Granted +${creditAdjustment} credits to ${adjustingUser.email}`);
      setUsersList((prev) =>
        prev.map((u) =>
          u.id === adjustingUser.id
            ? {
                ...u,
                credit_allowance: res.credit_allowance,
                credits_remaining: res.credits_remaining,
              }
            : u
        )
      );
      setAdjustingUser(null);
    } catch (err: any) {
      setError(err.message || "Failed to adjust credits.");
    } finally {
      setCreditUpdating(false);
    }
  }

  async function handleToggleRevoke(targetUser: AdminUserItem) {
    const isRevoked = targetUser.status === "revoked";
    const confirmMsg = isRevoked
      ? `Re-activate access for ${targetUser.email}?`
      : `Revoke access for ${targetUser.email}? This will invalidate all their active sessions.`;

    if (!confirm(confirmMsg)) return;

    try {
      setError("");
      setActionSuccess("");
      if (isRevoked) {
        await activateUserApi(targetUser.id);
        setActionSuccess(`Re-activated ${targetUser.email}`);
      } else {
        await revokeUserApi(targetUser.id);
        setActionSuccess(`Revoked ${targetUser.email}`);
      }
      setUsersList((prev) =>
        prev.map((u) =>
          u.id === targetUser.id
            ? { ...u, status: isRevoked ? "active" : "revoked" }
            : u
        )
      );
    } catch (err: any) {
      setError(err.message || "Failed to update user status.");
    }
  }

  const totalCreditsAllocated = usersList.reduce((acc, u) => acc + u.credit_allowance, 0);
  const totalCreditsUsed = usersList.reduce((acc, u) => acc + u.credits_used, 0);
  const pendingInvitesCount = invitesList.filter((i) => i.status === "pending").length;

  return (
    <div className="min-h-screen bg-zinc-950 text-white selection:bg-violet-500 selection:text-white">
      {/* Top Header */}
      <header className="sticky top-0 z-30 border-b border-white/10 bg-zinc-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/")}
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:text-white hover:bg-white/10 transition"
            >
              <ArrowLeft className="h-4 w-4" />
              Studio
            </button>
            <button
              onClick={() => router.push("/projects")}
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:text-white hover:bg-white/10 transition"
            >
              <FolderOpen className="h-4 w-4" />
              My Projects
            </button>
            <div className="flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center rounded-lg border border-amber-500/40 bg-amber-500/15 font-display text-sm font-black text-amber-300">
                <Shield className="h-4 w-4" />
              </div>
              <h1 className="font-display text-base font-bold text-white">Admin Management</h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={loadData}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:text-white hover:bg-white/10 transition"
              title="Refresh data"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-6xl px-6 py-10 space-y-8">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white font-display">
            User Accounts & Credit Quotas
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Monitor registered beta testers, manage video credit allowances, and dispatch invitations.
          </p>
        </div>

        {/* Alerts */}
        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
            {error}
          </div>
        )}
        {actionSuccess && (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-400 flex items-center justify-between">
            <span>{actionSuccess}</span>
            <button
              onClick={() => setActionSuccess("")}
              className="text-emerald-400 hover:text-white text-xs font-semibold"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* KPI Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 space-y-2">
            <div className="flex items-center justify-between text-zinc-400">
              <span className="text-xs font-medium uppercase tracking-wider">Registered Users</span>
              <Users className="h-4 w-4 text-violet-400" />
            </div>
            <div className="text-2xl font-bold text-white font-display">{usersList.length}</div>
            <p className="text-xs text-zinc-500">Active accounts in PostgreSQL</p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 space-y-2">
            <div className="flex items-center justify-between text-zinc-400">
              <span className="text-xs font-medium uppercase tracking-wider">Credits Allocated</span>
              <Sparkles className="h-4 w-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-white font-display">{totalCreditsAllocated}</div>
            <p className="text-xs text-zinc-500">Total allowance across all users</p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 space-y-2">
            <div className="flex items-center justify-between text-zinc-400">
              <span className="text-xs font-medium uppercase tracking-wider">Credits Consumed</span>
              <UserCheck className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-white font-display">{totalCreditsUsed}</div>
            <p className="text-xs text-zinc-500">Videos & transcriptions rendered</p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 space-y-2">
            <div className="flex items-center justify-between text-zinc-400">
              <span className="text-xs font-medium uppercase tracking-wider">Pending Invites</span>
              <Mail className="h-4 w-4 text-blue-400" />
            </div>
            <div className="text-2xl font-bold text-white font-display">{pendingInvitesCount}</div>
            <p className="text-xs text-zinc-500">Awaiting user registration</p>
          </div>
        </div>

        {/* Tab Controls & Inline Invite Section */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab("users")}
              className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition ${
                activeTab === "users"
                  ? "bg-violet-600 text-white shadow-lg shadow-violet-600/30"
                  : "bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10"
              }`}
            >
              <Users className="h-4 w-4" />
              Users & Quotas ({usersList.length})
            </button>
            <button
              onClick={() => setActiveTab("invites")}
              className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition ${
                activeTab === "invites"
                  ? "bg-violet-600 text-white shadow-lg shadow-violet-600/30"
                  : "bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10"
              }`}
            >
              <Mail className="h-4 w-4" />
              Invitations ({invitesList.length})
            </button>
          </div>

          {/* Quick Invite Form */}
          <form onSubmit={handleSendInvite} className="flex items-center gap-2">
            <input
              type="email"
              required
              placeholder="artist@label.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white placeholder-zinc-500 focus:border-violet-500 focus:outline-none w-48 sm:w-60"
            />
            <input
              type="number"
              min={1}
              max={100}
              value={inviteCredits}
              onChange={(e) => setInviteCredits(Number(e.target.value))}
              title="Credits allowance"
              className="rounded-xl border border-white/10 bg-white/5 px-2.5 py-2 text-xs text-white focus:border-violet-500 focus:outline-none w-16 text-center"
            />
            <button
              type="submit"
              disabled={inviteLoading}
              className="inline-flex items-center gap-1.5 rounded-xl bg-violet-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-violet-500 transition shadow-lg shadow-violet-600/20"
            >
              <Send className="h-3.5 w-3.5" />
              {inviteLoading ? "Sending..." : "Invite"}
            </button>
          </form>
        </div>

        {/* Tab 1: Users Table */}
        {activeTab === "users" && (
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] overflow-hidden shadow-2xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-white/5 text-zinc-400 border-b border-white/10">
                  <tr>
                    <th className="px-6 py-3.5 font-semibold">User</th>
                    <th className="px-6 py-3.5 font-semibold">Role</th>
                    <th className="px-6 py-3.5 font-semibold">Status</th>
                    <th className="px-6 py-3.5 font-semibold">Credits Available</th>
                    <th className="px-6 py-3.5 font-semibold">Used / Allowance</th>
                    <th className="px-6 py-3.5 font-semibold">Projects</th>
                    <th className="px-6 py-3.5 font-semibold">Joined</th>
                    <th className="px-6 py-3.5 font-semibold text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-zinc-300">
                  {usersList.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-6 py-10 text-center text-zinc-500">
                        No users registered yet.
                      </td>
                    </tr>
                  ) : (
                    usersList.map((u) => {
                      const joinedDate = new Date(u.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      });

                      return (
                        <tr key={u.id} className="hover:bg-white/[0.03] transition">
                          <td className="px-6 py-4 font-semibold text-white">{u.email}</td>
                          <td className="px-6 py-4">
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider border ${
                                u.role === "admin"
                                  ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                                  : "bg-zinc-800 text-zinc-300 border-white/10"
                              }`}
                            >
                              {u.role === "admin" && <Shield className="h-3 w-3" />}
                              {u.role}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider border ${
                                u.status === "active"
                                  ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                                  : "bg-red-500/15 text-red-300 border-red-500/30"
                              }`}
                            >
                              {u.status === "active" ? (
                                <CheckCircle2 className="h-3 w-3" />
                              ) : (
                                <XCircle className="h-3 w-3" />
                              )}
                              {u.status}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="font-bold text-violet-400">
                              ⚡ {u.credits_remaining} credits
                            </span>
                          </td>
                          <td className="px-6 py-4 text-zinc-400">
                            {u.credits_used} / {u.credit_allowance}
                          </td>
                          <td className="px-6 py-4 text-zinc-300">{u.projects_count} drafts</td>
                          <td className="px-6 py-4 text-zinc-400">{joinedDate}</td>
                          <td className="px-6 py-4 text-right space-x-2">
                            <button
                              onClick={() => setAdjustingUser(u)}
                              className="rounded-lg border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-[11px] font-semibold text-violet-300 hover:bg-violet-500/20 transition"
                            >
                              + Add Credits
                            </button>
                            {u.role !== "admin" && (
                              <button
                                onClick={() => handleToggleRevoke(u)}
                                className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold transition border ${
                                  u.status === "revoked"
                                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20"
                                    : "border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20"
                                }`}
                              >
                                {u.status === "revoked" ? "Re-activate" : "Revoke"}
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 2: Invitations Table */}
        {activeTab === "invites" && (
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] overflow-hidden shadow-2xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-white/5 text-zinc-400 border-b border-white/10">
                  <tr>
                    <th className="px-6 py-3.5 font-semibold">Invited Email</th>
                    <th className="px-6 py-3.5 font-semibold">Status</th>
                    <th className="px-6 py-3.5 font-semibold">Sent Date</th>
                    <th className="px-6 py-3.5 font-semibold">Expiration</th>
                    <th className="px-6 py-3.5 font-semibold">Accepted At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-zinc-300">
                  {invitesList.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-10 text-center text-zinc-500">
                        No invitations sent yet. Use the form above to invite beta users.
                      </td>
                    </tr>
                  ) : (
                    invitesList.map((inv) => {
                      const sentDate = new Date(inv.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      });
                      const expireDate = new Date(inv.expires_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      });
                      const acceptedDate = inv.accepted_at
                        ? new Date(inv.accepted_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })
                        : "—";

                      return (
                        <tr key={inv.id} className="hover:bg-white/[0.03] transition">
                          <td className="px-6 py-4 font-semibold text-white">{inv.email}</td>
                          <td className="px-6 py-4">
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider border ${
                                inv.status === "accepted"
                                  ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                                  : inv.status === "expired"
                                  ? "bg-red-500/15 text-red-300 border-red-500/30"
                                  : "bg-amber-500/15 text-amber-300 border-amber-500/30"
                              }`}
                            >
                              {inv.status === "accepted" ? (
                                <CheckCircle2 className="h-3 w-3" />
                              ) : inv.status === "expired" ? (
                                <XCircle className="h-3 w-3" />
                              ) : (
                                <Clock className="h-3 w-3" />
                              )}
                              {inv.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-zinc-400">{sentDate}</td>
                          <td className="px-6 py-4 text-zinc-400">{expireDate}</td>
                          <td className="px-6 py-4 text-zinc-300">{acceptedDate}</td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* Credit Adjustment Modal */}
      {adjustingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-zinc-900 p-6 space-y-5 shadow-2xl">
            <div>
              <h3 className="font-display font-bold text-base text-white">Adjust Credits</h3>
              <p className="text-xs text-zinc-400 mt-1 truncate">
                Grant additional video credits to <span className="text-white">{adjustingUser.email}</span>
              </p>
            </div>

            <form onSubmit={handleAdjustCredits} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">
                  Add Credits Amount
                </label>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={creditAdjustment}
                  onChange={(e) => setCreditAdjustment(Number(e.target.value))}
                  className="w-full rounded-xl border border-white/10 bg-zinc-950 px-3.5 py-2 text-sm text-white focus:border-violet-500 focus:outline-none"
                />
                <p className="text-[11px] text-zinc-500 mt-1.5">
                  Current allowance: {adjustingUser.credit_allowance} (Remaining: {adjustingUser.credits_remaining})
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setAdjustingUser(null)}
                  className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-zinc-300 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creditUpdating}
                  className="rounded-xl bg-violet-600 px-4 py-2 text-xs font-semibold text-white hover:bg-violet-500 transition shadow-lg shadow-violet-600/30"
                >
                  {creditUpdating ? "Granting..." : "Grant Credits"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

