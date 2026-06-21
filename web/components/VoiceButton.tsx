"use client";

import { useRef, useState } from "react";

type VoiceButtonProps = {
  onTranscript: (text: string) => void;
};

export function VoiceButton({ onTranscript }: VoiceButtonProps) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function startRecording() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        await transcribe(blob);
      };

      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (err) {
      setError("Microphone access denied");
      console.error(err);
    }
  }

  function stopRecording() {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    setRecording(false);
  }

  async function transcribe(blob: Blob) {
    setBusy(true);
    try {
      const response = await fetch("/api/voice/transcribe", {
        method: "POST",
        headers: { "content-type": blob.type || "audio/webm" },
        body: blob,
      });
      if (!response.ok) throw new Error(`Transcribe failed: ${response.status}`);
      const { transcript } = await response.json();
      if (transcript) onTranscript(transcript);
    } catch (err) {
      setError("Could not transcribe audio");
      console.error(err);
    } finally {
      setBusy(false);
    }
  }

  const label = busy ? "Transcribing…" : recording ? "Listening… release to send" : "Hold to speak";

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        disabled={busy}
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onMouseLeave={() => recording && stopRecording()}
        onTouchStart={(event) => {
          event.preventDefault();
          startRecording();
        }}
        onTouchEnd={(event) => {
          event.preventDefault();
          stopRecording();
        }}
        className={`select-none rounded-md border px-4 py-2 ${
          recording ? "border-red-500 bg-red-50 text-red-700" : "bg-white"
        } ${busy ? "opacity-60" : ""}`}
      >
        {label}
      </button>
      {error ? <span className="text-sm text-red-600">{error}</span> : null}
    </div>
  );
}
