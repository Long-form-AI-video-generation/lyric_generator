"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Clock, Download, FileAudio, FolderOpen, Music, Play, Plus, Shield, Trash2 } from "lucide-react";
import { useAuthStore } from "@/store/useAuthStore";
import { useAppStore } from "@/store/useAppStore";
import { deleteProjectApi, downloadUrl, fetchProjectsApi } from "@/lib/api";
import type { ProjectItem } from "@/lib/types";

export default function ProjectsPage() {
  const router = useRouter();
  const { user, token } = useAuthStore();
  const { loadProject, reset } = useAppStore();

  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      router.push("/login");
      return;
    }

    async function load() {
      try {
        setLoading(true);
        const data = await fetchProjectsApi();
        setProjects(data);
      } catch (err: any) {
        setError(err.message || "Failed to load projects.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [token, router]);

  function handleResume(project: ProjectItem) {
    loadProject(project);
    router.push("/");
  }

  function handleCreateNew() {
    reset();
    router.push("/");
  }

  async function handleDelete(projectId: string) {
    if (!confirm("Are you sure you want to delete this project draft?")) return;
    try {
      setDeletingId(projectId);
      await deleteProjectApi(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
    } catch (err: any) {
      alert(err.message || "Failed to delete project.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white selection:bg-violet-500 selection:text-white">
      {/* Top Navigation */}
      <header className="sticky top-0 z-30 border-b border-white/10 bg-zinc-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/")}
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:text-white hover:bg-white/10 transition"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Wizard
            </button>
            <div className="flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center rounded-lg border border-violet-500/40 bg-violet-500/15 font-display text-sm font-black text-white">
                LV
              </div>
              <h1 className="font-display text-base font-bold text-white">My Projects</h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {user?.role === "admin" && (
              <button
                onClick={() => router.push("/admin/users")}
                className="inline-flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 transition"
              >
                <Shield className="h-3.5 w-3.5" />
                Admin Panel
              </button>
            )}
            {user && (
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs font-semibold text-violet-300">
                ⚡ {user.credits_remaining} credits
              </span>
            )}
            <button
              onClick={handleCreateNew}
              className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-xs font-semibold text-white hover:bg-violet-500 shadow-lg shadow-violet-600/30 transition"
            >
              <Plus className="h-4 w-4" />
              New Video
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex flex-col gap-2 pb-8">
          <h2 className="text-2xl font-bold tracking-tight text-white font-display">Saved Video Drafts</h2>
          <p className="text-sm text-zinc-400">
            Resume saved lyric projects, review past storyboard scenes, or continue editing.
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-zinc-400">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
            <p className="text-sm">Loading your projects...</p>
          </div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] py-20 text-center">
            <div className="grid h-16 w-16 place-items-center rounded-2xl border border-violet-500/30 bg-violet-500/10 text-violet-400 mb-4">
              <FolderOpen className="h-8 w-8" />
            </div>
            <h3 className="text-base font-semibold text-white">No projects found</h3>
            <p className="mt-1 text-sm text-zinc-400 max-w-sm">
              Upload an audio file in the wizard to start generating synchronized lyric videos.
            </p>
            <button
              onClick={handleCreateNew}
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-violet-500 transition"
            >
              <Plus className="h-4 w-4" />
              Create Your First Video
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((project) => {
              const lineCount = project.lyrics?.timing_data?.length || 0;
              const sceneCount = project.scenes?.length || 0;
              const formattedDate = new Date(project.created_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              });

              return (
                <div
                  key={project.id}
                  className="group relative flex flex-col justify-between rounded-2xl border border-white/10 bg-white/[0.03] p-5 hover:border-violet-500/40 hover:bg-white/[0.05] transition shadow-xl"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <div className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 bg-zinc-900 text-violet-400">
                          <Music className="h-5 w-5" />
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-white truncate max-w-[180px]">
                            {project.title}
                          </h3>
                          <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                            <Clock className="h-3 w-3" />
                            <span>{formattedDate}</span>
                          </div>
                        </div>
                      </div>

                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider border ${
                          project.status === "completed"
                            ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                            : "bg-amber-500/15 text-amber-300 border-amber-500/30"
                        }`}
                      >
                        {project.status}
                      </span>
                    </div>

                    {/* Metadata Pill Badges */}
                    <div className="flex flex-wrap items-center gap-2 pt-2">
                      <span className="inline-flex items-center gap-1 rounded-lg border border-white/5 bg-white/5 px-2.5 py-1 text-[11px] text-zinc-300">
                        <FileAudio className="h-3 w-3 text-zinc-400" />
                        {lineCount > 0 ? `${lineCount} lyric lines` : "No lyrics parsed"}
                      </span>
                      {sceneCount > 0 && (
                        <span className="inline-flex items-center gap-1 rounded-lg border border-white/5 bg-white/5 px-2.5 py-1 text-[11px] text-zinc-300">
                          🎬 {sceneCount} scenes
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="mt-6 flex items-center justify-between border-t border-white/5 pt-4">
                    <button
                      onClick={() => handleDelete(project.id)}
                      disabled={deletingId === project.id}
                      className="rounded-lg p-2 text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition"
                      title="Delete draft"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>

                    <div className="flex items-center gap-2">
                      {project.status === "completed" && (
                        <a
                          href={downloadUrl(project.id)}
                          className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/40 bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-500 hover:text-white transition"
                          title="Download MP4 video"
                        >
                          <Download className="h-3.5 w-3.5" />
                          Download
                        </a>
                      )}

                      <button
                        onClick={() => handleResume(project)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-violet-500/40 bg-violet-500/15 px-3.5 py-1.5 text-xs font-semibold text-violet-200 hover:bg-violet-500 hover:text-white transition"
                      >
                        <Play className="h-3.5 w-3.5" />
                        {project.status === "completed" ? "Open Studio" : "Resume"}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

