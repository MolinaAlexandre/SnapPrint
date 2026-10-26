"use client";

import { useRef, useState } from "react";

type Props = {
  onRecorded: (blob: Blob) => void;
};

export default function VoiceRecorder({ onRecorded }: Props) {
  const [recording, setRecording] = useState(false);
  const [hasClip, setHasClip] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setHasClip(true);
        onRecorded(blob);
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (err) {
      alert("Micro inaccessible : " + (err as Error).message);
    }
  };

  const stop = () => {
    recorderRef.current?.stop();
    setRecording(false);
  };

  return (
    <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
      <button
        type="button"
        onClick={recording ? stop : start}
        style={{
          padding: "0.6rem 1.1rem",
          borderRadius: "8px",
          border: "none",
          cursor: "pointer",
          background: recording ? "#e74c3c" : "#4f9dff",
          color: "white",
          fontWeight: 600,
        }}
      >
        {recording ? "⏹ Arrêter" : "🎤 Enregistrer la consigne"}
      </button>
      {hasClip && !recording && (
        <span style={{ color: "#4caf50" }}>✓ Consigne enregistrée</span>
      )}
    </div>
  );
}
