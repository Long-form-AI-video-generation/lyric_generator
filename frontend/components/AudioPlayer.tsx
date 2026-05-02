"use client";

import { Pause, Play } from "lucide-react";
import { useEffect, useState } from "react";
import type { RefObject } from "react";
import { formatDuration } from "@/lib/utils";
import { Button } from "@/components/ui/Button";

type AudioPlayerProps = {
  src: string;
  audioRef: RefObject<HTMLAudioElement>;
  onTimeChange: (time: number) => void;
  onPlayingChange: (playing: boolean) => void;
};

export function AudioPlayer({ src, audioRef, onTimeChange, onPlayingChange }: AudioPlayerProps) {
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const handleTime = () => {
      setCurrentTime(audio.currentTime);
      onTimeChange(audio.currentTime);
    };
    const handleDuration = () => setDuration(audio.duration || 0);
    const handleEnded = () => {
      setPlaying(false);
      onPlayingChange(false);
    };
    audio.addEventListener("timeupdate", handleTime);
    audio.addEventListener("loadedmetadata", handleDuration);
    audio.addEventListener("ended", handleEnded);
    return () => {
      audio.removeEventListener("timeupdate", handleTime);
      audio.removeEventListener("loadedmetadata", handleDuration);
      audio.removeEventListener("ended", handleEnded);
    };
  }, [audioRef, onPlayingChange, onTimeChange]);

  async function togglePlayback() {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      await audio.play();
      setPlaying(true);
      onPlayingChange(true);
    } else {
      audio.pause();
      setPlaying(false);
      onPlayingChange(false);
    }
  }

  function seek(value: number) {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = value;
    setCurrentTime(value);
    onTimeChange(value);
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <audio ref={audioRef} src={src} preload="metadata" />
      <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3">
        <Button variant="secondary" className="h-10 w-10 px-0" onClick={togglePlayback} aria-label={playing ? "Pause" : "Play"}>
          {playing ? <Pause className="h-4 w-4" aria-hidden /> : <Play className="h-4 w-4" aria-hidden />}
        </Button>
        <input
          aria-label="Playback position"
          type="range"
          min={0}
          max={duration || 0}
          step={0.01}
          value={currentTime}
          onChange={(event) => seek(Number(event.target.value))}
          className="h-2 w-full"
        />
        <div className="w-28 text-right text-sm tabular-nums text-zinc-300">
          {formatDuration(currentTime)} / {formatDuration(duration)}
        </div>
      </div>
    </div>
  );
}
