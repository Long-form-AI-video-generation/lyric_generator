const audioInput = document.getElementById("audio-input");
const jsonInput = document.getElementById("json-input");
const audioButton = document.getElementById("audio-button");
const jsonButton = document.getElementById("json-button");
const audioDropzone = document.getElementById("audio-dropzone");
const jsonDropzone = document.getElementById("json-dropzone");
const audioFilename = document.getElementById("audio-filename");
const jsonFilename = document.getElementById("json-filename");
const statusBox = document.getElementById("status-box");
const audioStatus = document.getElementById("audio-status");
const lyricsStatus = document.getElementById("lyrics-status");
const activeIndex = document.getElementById("active-index");
const audioPlayer = document.getElementById("audio-player");
const activeLine = document.getElementById("active-line");
const previousLine = document.getElementById("previous-line");
const nextLine = document.getElementById("next-line");
const currentTimeEl = document.getElementById("current-time");
const totalTimeEl = document.getElementById("total-time");
const timelineProgress = document.getElementById("timeline-progress");
const activeRange = document.getElementById("active-range");
const activeConfidence = document.getElementById("active-confidence");
const lineList = document.getElementById("line-list");
const lineItemTemplate = document.getElementById("line-item-template");

let lyricsData = [];
let activeLineIndex = -1;
let rafId = null;
let audioObjectUrl = null;

const formatTime = (seconds) => {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "00:00.0";
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds - minutes * 60;
  return `${String(minutes).padStart(2, "0")}:${remainingSeconds
    .toFixed(1)
    .padStart(4, "0")}`;
};

const updateStatus = (message, tone = "default") => {
  statusBox.textContent = message;
  statusBox.dataset.tone = tone;
};

const markDropzone = (element, isActive) => {
  element.classList.toggle("is-dragover", isActive);
};

const clearVisualizer = () => {
  activeLineIndex = -1;
  activeLine.textContent = "Upload files to begin preview.";
  previousLine.textContent = "Previous line";
  nextLine.textContent = "Next line";
  activeIndex.textContent = "--";
  activeRange.textContent = "--";
  activeConfidence.textContent = "Confidence --";
  timelineProgress.style.width = "0%";
  lineList.innerHTML = "";
};

const validateLyricsJson = (payload) => {
  if (!Array.isArray(payload)) {
    throw new Error("Top-level JSON must be an array of lyric lines.");
  }

  payload.forEach((entry, index) => {
    if (typeof entry !== "object" || entry === null) {
      throw new Error(`Entry ${index} is not a valid object.`);
    }

    const requiredFields = ["line_index", "line", "start", "end"];
    requiredFields.forEach((field) => {
      if (!(field in entry)) {
        throw new Error(`Entry ${index} is missing "${field}".`);
      }
    });

    if (typeof entry.line !== "string") {
      throw new Error(`Entry ${index} has a non-string line value.`);
    }

    if (!Number.isFinite(Number(entry.start)) || !Number.isFinite(Number(entry.end))) {
      throw new Error(`Entry ${index} has invalid timing values.`);
    }
  });

  return payload
    .map((entry) => ({
      line_index: Number(entry.line_index),
      line: entry.line,
      start: Number(entry.start),
      end: Number(entry.end),
      confidence: Number.isFinite(Number(entry.confidence))
        ? Number(entry.confidence)
        : null,
    }))
    .sort((left, right) => left.start - right.start);
};

const loadAudioFile = (file) => {
  if (!file) {
    return;
  }

  audioFilename.textContent = file.name;
  audioStatus.textContent = "Loaded";

  if (audioObjectUrl) {
    URL.revokeObjectURL(audioObjectUrl);
  }

  audioObjectUrl = URL.createObjectURL(file);
  audioPlayer.src = audioObjectUrl;
  audioPlayer.load();
  updateStatus(
    lyricsData.length
      ? "Audio ready. Press play to preview the synced lines."
      : "Audio ready. Upload the lyrics JSON to complete the preview.",
    audioObjectUrl && lyricsData.length ? "ready" : "default",
  );
};

const loadJsonFile = async (file) => {
  if (!file) {
    return;
  }

  jsonFilename.textContent = file.name;

  try {
    const rawText = await file.text();
    lyricsData = validateLyricsJson(JSON.parse(rawText));
    clearVisualizer();
    renderLineList();
    lyricsStatus.textContent = `${lyricsData.length} lines`;
    updateStatus(
      audioPlayer.src
        ? "Lyrics loaded. Press play to preview the timed lines."
        : "Lyrics loaded. Upload the song file to start playback.",
      "ready",
    );
    syncActiveLine();
  } catch (error) {
    lyricsData = [];
    clearVisualizer();
    lyricsStatus.textContent = "Invalid file";
    updateStatus(error.message || "Could not parse the lyrics JSON.", "error");
  }
};

const renderLineList = () => {
  lineList.innerHTML = "";

  lyricsData.forEach((entry, index) => {
    const node = lineItemTemplate.content.firstElementChild.cloneNode(true);
    node.dataset.index = String(index);
    node.querySelector(".line-index").textContent = `#${entry.line_index}`;
    node.querySelector(".line-text").textContent = entry.line;
    node.querySelector(".line-time").textContent = `${formatTime(entry.start)} - ${formatTime(
      entry.end,
    )}`;
    node.addEventListener("click", () => {
      audioPlayer.currentTime = entry.start;
      audioPlayer.play().catch(() => {});
      syncActiveLine();
    });
    lineList.appendChild(node);
  });
};

const setActiveLine = (index) => {
  if (activeLineIndex === index) {
    return;
  }

  activeLineIndex = index;
  const entries = Array.from(lineList.children);
  entries.forEach((node, nodeIndex) => {
    node.classList.toggle("active", nodeIndex === index);
  });

  if (index < 0 || !lyricsData[index]) {
    activeLine.textContent = "Waiting for the next lyric line.";
    previousLine.textContent = "Previous line";
    nextLine.textContent = lyricsData[0]?.line || "Next line";
    activeIndex.textContent = "--";
    activeRange.textContent = "--";
    activeConfidence.textContent = "Confidence --";
    return;
  }

  const current = lyricsData[index];
  const previous = lyricsData[index - 1];
  const next = lyricsData[index + 1];

  activeLine.textContent = current.line;
  previousLine.textContent = previous?.line || " ";
  nextLine.textContent = next?.line || " ";
  activeIndex.textContent = `#${current.line_index}`;
  activeRange.textContent = `${formatTime(current.start)} - ${formatTime(current.end)}`;
  activeConfidence.textContent =
    current.confidence === null ? "Confidence --" : `Confidence ${current.confidence.toFixed(2)}`;

  const activeNode = lineList.children[index];
  activeNode?.scrollIntoView({ block: "nearest", behavior: "smooth" });
};

const findActiveLineIndex = (time) =>
  lyricsData.findIndex((entry) => time >= entry.start && time <= entry.end);

const syncActiveLine = () => {
  currentTimeEl.textContent = formatTime(audioPlayer.currentTime);
  totalTimeEl.textContent = formatTime(audioPlayer.duration);

  const progressPercent = audioPlayer.duration
    ? (audioPlayer.currentTime / audioPlayer.duration) * 100
    : 0;
  timelineProgress.style.width = `${Math.min(100, Math.max(0, progressPercent))}%`;

  const nextIndex = findActiveLineIndex(audioPlayer.currentTime);
  setActiveLine(nextIndex);

  if (!audioPlayer.paused) {
    rafId = requestAnimationFrame(syncActiveLine);
  }
};

const stopSyncLoop = () => {
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
};

audioPlayer.addEventListener("play", () => {
  stopSyncLoop();
  syncActiveLine();
});

audioPlayer.addEventListener("pause", stopSyncLoop);
audioPlayer.addEventListener("ended", () => {
  stopSyncLoop();
  syncActiveLine();
});
audioPlayer.addEventListener("seeked", syncActiveLine);
audioPlayer.addEventListener("loadedmetadata", syncActiveLine);

audioButton.addEventListener("click", () => {
  audioInput.value = "";
  audioInput.click();
});

jsonButton.addEventListener("click", () => {
  jsonInput.value = "";
  jsonInput.click();
});

audioInput.addEventListener("change", () => loadAudioFile(audioInput.files?.[0]));
jsonInput.addEventListener("change", () => loadJsonFile(jsonInput.files?.[0]));

const bindDropzone = (element, onFile) => {
  ["dragenter", "dragover"].forEach((eventName) => {
    element.addEventListener(eventName, (event) => {
      event.preventDefault();
      markDropzone(element, true);
    });
  });

  ["dragleave", "dragend", "drop"].forEach((eventName) => {
    element.addEventListener(eventName, (event) => {
      event.preventDefault();
      markDropzone(element, false);
    });
  });

  element.addEventListener("drop", (event) => {
    const [file] = event.dataTransfer?.files || [];
    onFile(file);
  });
};

bindDropzone(audioDropzone, loadAudioFile);
bindDropzone(jsonDropzone, loadJsonFile);

clearVisualizer();
currentTimeEl.textContent = formatTime(0);
totalTimeEl.textContent = formatTime(0);
