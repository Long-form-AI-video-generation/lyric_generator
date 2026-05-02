import type { LyricsFile } from "@/lib/types";
import { normalizeLyricsIds } from "@/lib/utils";

type JsonObject = Record<string, unknown>;

function asObject(value: unknown, path: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${path} must be an object.`);
  }
  return value as JsonObject;
}

function numericField(item: JsonObject, field: string, path: string) {
  const value = Number(item[field]);
  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`${path}.${field} must be a non-negative number.`);
  }
  return value;
}

function lineText(item: JsonObject, path: string) {
  const text = item.text ?? item.line;
  if (typeof text !== "string" || !text.trim()) {
    throw new Error(`${path}.text is required.`);
  }
  return text.trim();
}

function lineId(item: JsonObject, index: number) {
  const legacyIndex = Number(item.line_index);
  const id = Number(item.id);
  if (Number.isInteger(id) && id > 0) return id;
  if (Number.isInteger(legacyIndex) && legacyIndex >= 0) return legacyIndex + 1;
  return index + 1;
}

export function parseLyricsJson(value: unknown): LyricsFile {
  const payload = Array.isArray(value) ? { lines: value } : asObject(value, "JSON");
  const rawLines = payload.lines;

  if (!Array.isArray(rawLines) || rawLines.length === 0) {
    throw new Error("lines must contain at least one row.");
  }

  const lines = rawLines.map((line, index) => {
    const item = asObject(line, `lines.${index}`);
    const start = numericField(item, "start", `lines.${index}`);
    const end = numericField(item, "end", `lines.${index}`);
    if (end <= start) {
      throw new Error(`lines.${index}.end must be greater than start.`);
    }
    return {
      id: lineId(item, index),
      text: lineText(item, `lines.${index}`),
      start,
      end
    };
  });

  const title = typeof payload.title === "string" && payload.title.trim()
    ? payload.title.trim()
    : "Untitled Song";
  const duration = Number(payload.duration_seconds);

  return {
    title,
    duration_seconds: Number.isFinite(duration) && duration >= 0 ? duration : lines.at(-1)?.end ?? 0,
    lines: normalizeLyricsIds(lines)
  };
}

