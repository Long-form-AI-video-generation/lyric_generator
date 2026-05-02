"use client";

import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type StatusBannerProps = {
  tone?: "error" | "success" | "info";
  children: ReactNode;
};

export function StatusBanner({ tone = "info", children }: StatusBannerProps) {
  const Icon = tone === "error" ? AlertTriangle : tone === "success" ? CheckCircle2 : Info;
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "flex items-start gap-3 rounded-lg border px-4 py-3 text-sm",
        tone === "error" && "border-red-500/40 bg-red-500/10 text-red-100",
        tone === "success" && "border-emerald-500/40 bg-emerald-500/10 text-emerald-100",
        tone === "info" && "border-border bg-surface text-zinc-200"
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 flex-none" aria-hidden />
      <div>{children}</div>
    </div>
  );
}
