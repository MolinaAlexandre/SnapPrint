"use client";

import { useState } from "react";
import ThreeViewer from "@/components/ThreeViewer";
import VoiceRecorder from "@/components/VoiceRecorder";

type GenerateResponse = {
  job_id: string;
  transcript: string;
  metric: { width_mm: number; depth_mm: number; px_to_mm: number };
  success: boolean;
  attempts: number;
  scad_code: string;
  errors: string[];
  stl_url: string | null;
};

export default function Home() {
  const [photo, setPhoto] = useState<File | null>(null);
  const [audio, setAudio] = useState<Blob | null>(null);
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stlUrl = result?.stl_url ?? null;

  const submit = async () => {
    if (!photo) {
      setError("Ajoute une photo de l'objet (avec une pièce de 1 € pour l'échelle).");
      return;
    }
    if (!audio && !instruction.trim()) {
      setError("Enregistre une consigne vocale ou écris une instruction.");
      return;
    }
    setError(null);
    setLoading(true);
    setResult(null);

    try {
      const form = new FormData();
      form.append("photo", photo);
      if (audio) form.append("audio", audio, "consigne.webm");
      else form.append("instruction", instruction);

      const res = await fetch("/api/generate", { method: "POST", body: form });
      const data: GenerateResponse = await res.json();
      setResult(data);
      if (!data.success) {
        setError("Compilation échouée après auto-correction. Voir les détails.");
      }
    } catch (e) {
      setError("Erreur réseau : " + (e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "2rem 1.5rem" }}>
      <h1 style={{ fontSize: "2rem", marginBottom: "0.25rem" }}>
        SnapPrint <span style={{ color: "#4f9dff" }}>/ VoiceCAD</span>
      </h1>
      <p style={{ color: "#9aa0aa", marginTop: 0 }}>
        Photographie un objet avec une pièce de 1 € pour l'échelle, décris ce que
        tu veux, et récupère un STL imprimable.
      </p>

      <section
        style={{
          display: "grid",
          gap: "1.25rem",
          background: "#14161c",
          padding: "1.5rem",
          borderRadius: "12px",
          marginTop: "1.5rem",
        }}
      >
        <div>
          <label style={{ display: "block", marginBottom: "0.5rem" }}>
            1. Photo de l'objet (+ pièce 1 €)
          </label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
          />
        </div>

        <div>
          <label style={{ display: "block", marginBottom: "0.5rem" }}>
            2. Consigne vocale
          </label>
          <VoiceRecorder onRecorded={setAudio} />
          <p style={{ color: "#6b7280", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            …ou écris l'instruction :
          </p>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="Ex : un dock incliné pour ma souris avec passage de câble"
            rows={2}
            style={{
              width: "100%",
              background: "#0f1116",
              color: "#e8e8e8",
              border: "1px solid #2a2d35",
              borderRadius: "8px",
              padding: "0.6rem",
            }}
          />
        </div>

        <button
          type="button"
          onClick={submit}
          disabled={loading}
          style={{
            padding: "0.8rem 1.2rem",
            borderRadius: "8px",
            border: "none",
            cursor: loading ? "default" : "pointer",
            background: loading ? "#2a2d35" : "#4f9dff",
            color: "white",
            fontWeight: 700,
            fontSize: "1rem",
          }}
        >
          {loading ? "Génération en cours…" : "⚙️ Générer le modèle 3D"}
        </button>

        {error && <p style={{ color: "#ff6b6b", margin: 0 }}>{error}</p>}
      </section>

      {result && (
        <section style={{ marginTop: "1.5rem" }}>
          <h2 style={{ fontSize: "1.2rem" }}>Résultat</h2>
          <p style={{ color: "#9aa0aa" }}>
            Transcription : « {result.transcript} » — bbox{" "}
            {result.metric.width_mm} × {result.metric.depth_mm} mm — tentatives :{" "}
            {result.attempts}
          </p>
          <ThreeViewer stlUrl={stlUrl} />
          {stlUrl && (
            <p style={{ marginTop: "0.75rem" }}>
              <a href={stlUrl} download style={{ color: "#4f9dff" }}>
                ⬇️ Télécharger le STL
              </a>
            </p>
          )}
          <details style={{ marginTop: "1rem" }}>
            <summary style={{ cursor: "pointer" }}>Code OpenSCAD généré</summary>
            <pre
              style={{
                background: "#0f1116",
                padding: "1rem",
                borderRadius: "8px",
                overflowX: "auto",
                fontSize: "0.8rem",
              }}
            >
              {result.scad_code}
            </pre>
          </details>
          {result.errors.length > 0 && (
            <details>
              <summary style={{ cursor: "pointer", color: "#ff9f6b" }}>
                Erreurs de compilation ({result.errors.length})
              </summary>
              <pre
                style={{
                  background: "#0f1116",
                  padding: "1rem",
                  borderRadius: "8px",
                  overflowX: "auto",
                  fontSize: "0.8rem",
                  color: "#ff9f6b",
                }}
              >
                {result.errors.join("\n\n")}
              </pre>
            </details>
          )}
        </section>
      )}
    </main>
  );
}
