"use client";

import { Download, Plus, RotateCcw, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { parseLyricsJson } from "@/lib/lyrics";
import type { LyricsFile, LyricLine } from "@/lib/types";
import { normalizeLyricsIds } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { StatusBanner } from "@/components/ui/StatusBanner";

type LyricEditorProps = {
  lyrics: LyricsFile;
  onChange: (lyrics: LyricsFile) => void;
  onReset: () => void;
  onUploadLyrics: (lyrics: LyricsFile) => void;
};

export function LyricEditor({ lyrics, onChange, onReset, onUploadLyrics }: LyricEditorProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [jsonError, setJsonError] = useState("");

  function updateLine(id: number, patch: Partial<LyricLine>) {
    onChange({
      ...lyrics,
      lines: lyrics.lines.map((line) => (line.id === id ? { ...line, ...patch } : line))
    });
  }

  function addLine() {
    const previous = lyrics.lines.at(-1);
    const start = previous ? previous.end : 0;
    const end = start + 2;
    onChange({
      ...lyrics,
      lines: [...lyrics.lines, { id: lyrics.lines.length + 1, text: "New lyric line", start, end }]
    });
  }

  function deleteLine(id: number) {
    onChange({
      ...lyrics,
      lines: normalizeLyricsIds(lyrics.lines.filter((line) => line.id !== id))
    });
  }

  function downloadJson() {
    const blob = new Blob([JSON.stringify(lyrics, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${lyrics.title || "lyrics"}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function handleJsonUpload(file: File | undefined) {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      const next = parseLyricsJson(parsed);
      setJsonError("");
      onUploadLyrics(next);
    } catch (error) {
      setJsonError(error instanceof Error ? error.message : "The lyrics JSON could not be read.");
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="flex min-h-0 flex-col gap-4">
      <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-center">
        <label className="grid gap-2 text-sm font-medium text-zinc-200">
          Song title
          <input
            className="focus-ring h-10 rounded-lg border border-border bg-background px-3 text-text"
            value={lyrics.title}
            onChange={(event) => onChange({ ...lyrics, title: event.target.value })}
          />
        </label>
        <div className="flex flex-wrap gap-2 md:justify-end">
          <input ref={inputRef} type="file" accept="application/json,.json" className="hidden" onChange={(event) => handleJsonUpload(event.target.files?.[0])} />
          <Button variant="secondary" onClick={() => inputRef.current?.click()}>
            <Upload className="h-4 w-4" aria-hidden />
            JSON
          </Button>
          <Button variant="secondary" onClick={downloadJson}>
            <Download className="h-4 w-4" aria-hidden />
            JSON
          </Button>
          <Button variant="ghost" onClick={onReset}>
            <RotateCcw className="h-4 w-4" aria-hidden />
            Reset
          </Button>
          <Button onClick={addLine}>
            <Plus className="h-4 w-4" aria-hidden />
            Add Line
          </Button>
        </div>
      </div>
      {jsonError ? <StatusBanner tone="error">{jsonError}</StatusBanner> : null}
      <div className="min-h-[360px] overflow-auto rounded-lg border border-border">
        <table className="w-full min-w-[760px] border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-zinc-950 text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="w-14 px-3 py-3">#</th>
              <th className="px-3 py-3">Text</th>
              <th className="w-32 px-3 py-3">Start (s)</th>
              <th className="w-32 px-3 py-3">End (s)</th>
              <th className="w-14 px-3 py-3" aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {lyrics.lines.map((line, index) => (
              <tr key={line.id} className="group border-t border-border odd:bg-surface even:bg-surface2">
                <td className="px-3 py-2 text-muted">{index + 1}</td>
                <td className="px-3 py-2">
                  <input className="focus-ring h-9 w-full rounded-md border border-transparent bg-transparent px-2 text-text hover:border-border" value={line.text} onChange={(event) => updateLine(line.id, { text: event.target.value })} />
                </td>
                <td className="px-3 py-2">
                  <input className="focus-ring h-9 w-full rounded-md border border-border bg-background px-2 text-text" type="number" min={0} step={0.01} value={line.start} onChange={(event) => updateLine(line.id, { start: Number(event.target.value) })} />
                </td>
                <td className="px-3 py-2">
                  <input className="focus-ring h-9 w-full rounded-md border border-border bg-background px-2 text-text" type="number" min={0} step={0.01} value={line.end} onChange={(event) => updateLine(line.id, { end: Number(event.target.value) })} />
                </td>
                <td className="px-3 py-2">
                  <Button variant="ghost" className="h-9 w-9 px-0 opacity-70 md:opacity-0 md:group-hover:opacity-100" onClick={() => deleteLine(line.id)} aria-label={`Delete line ${index + 1}`}>
                    <Trash2 className="h-4 w-4" aria-hidden />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
