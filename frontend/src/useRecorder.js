import { useCallback, useRef, useState } from "react";

const MAX_SECONDS = 20;

function pickMime() {
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  return types.find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || "";
}

/** Mic recording hook. start() -> stop() returns a Blob. */
export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const recRef = useRef(null);
  const chunksRef = useRef([]);
  const resolveRef = useRef(null);
  const timerRef = useRef(null);

  const cleanup = () => {
    clearInterval(timerRef.current);
    recRef.current?.stream.getTracks().forEach((t) => t.stop());
    recRef.current = null;
    setRecording(false);
  };

  const stop = useCallback(() => {
    return new Promise((resolve) => {
      const rec = recRef.current;
      if (!rec) return resolve(null);
      resolveRef.current = resolve;
      if (rec.state !== "inactive") rec.stop();
    });
  }, []);

  const start = useCallback(async (onAutoStop) => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const mimeType = pickMime();
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    chunksRef.current = [];
    rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
    rec.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
      cleanup();
      resolveRef.current?.(blob);
      resolveRef.current = null;
    };
    recRef.current = rec;
    rec.start();
    setRecording(true);
    setSeconds(0);
    const t0 = Date.now();
    timerRef.current = setInterval(() => {
      const s = Math.floor((Date.now() - t0) / 1000);
      setSeconds(s);
      if (s >= MAX_SECONDS) {
        clearInterval(timerRef.current);
        onAutoStop?.();
      }
    }, 250);
  }, []);

  return { recording, seconds, start, stop };
}
