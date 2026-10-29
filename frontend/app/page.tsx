"use client";

import { useState } from "react";
import CodeEditor from "@/components/CodeEditor";
import VoiceRecorder from "@/components/VoiceRecorder";
import { apiUrl } from "@/lib/api";

type GenerateResponse = {
  job_id: string;
  transcript: string;
  metric: {
    width_mm: number;
    depth_mm: number;
    length_mm: number;
    px_to_mm: number;
    calibration: string;
  };
  success: boolean;
  attempts: number;
  scad_code: string;
  errors: string[];
  stl_url: string | null;
  parts_url: string | null;
};

export default function Home() {
  const [photo, setPhoto] = useState<File | null>(null);
  const [audio, setAudio] = useState<Blob | null>(null);
  const [instruction, setInstruction] = useState("");
  const [objectPrompt, setObjectPrompt] = useState("");
  const [realDim, setRealDim] = useState("");
  const [realDimAxis, setRealDimAxis] = useState("length");
  const [quality, setQuality] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      if (objectPrompt.trim()) form.append("object_prompt", objectPrompt.trim());
      form.append("quality", quality ? "true" : "false");
      const rd = parseFloat(realDim.replace(",", "."));
      if (!isNaN(rd) && rd > 0) {
        form.append("real_dim_mm", String(rd));
        form.append("real_dim_axis", realDimAxis);
      }

      const res = await fetch(apiUrl("/api/generate"), {
        method: "POST",
        body: form,
      });
      const data = await res.json();

      // Erreur FastAPI (400/422/…) : { detail: "..." }, sans metric. On ne doit
      // PAS la confondre avec un échec de compilation (500 mais avec metric +
      // scad_code + errors, qu'on veut afficher).
      if (!data || !data.metric) {
        const detail =
          (data && (data.detail || data.message)) ||
          `Échec (HTTP ${res.status}).`;
        setResult(null);
        setError(typeof detail === "string" ? detail : JSON.stringify(detail));
        return;
      }

      setResult(data as GenerateResponse);
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
            2. Objet à scanner
          </label>
          <input
            type="text"
            value={objectPrompt}
            onChange={(e) => setObjectPrompt(e.target.value)}
            placeholder="ex : computer mouse, phone, game controller"
            style={{
              width: "100%",
              background: "#0f1116",
              color: "#e8e8e8",
              border: "1px solid #2a2d35",
              borderRadius: "8px",
              padding: "0.6rem",
            }}
          />
          <p style={{ color: "#6b7280", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            En anglais, en quelques mots. Sert à détourer précisément l'objet sur
            la photo. Laisse vide pour la détection automatique.
          </p>
        </div>

        <div>
          <label style={{ display: "block", marginBottom: "0.5rem" }}>
            Dimension réelle connue (optionnel, mm)
          </label>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input
              type="number"
              min="0"
              step="0.1"
              value={realDim}
              onChange={(e) => setRealDim(e.target.value)}
              placeholder="ex : 135"
              style={{
                flex: 1,
                background: "#0f1116",
                color: "#e8e8e8",
                border: "1px solid #2a2d35",
                borderRadius: "8px",
                padding: "0.6rem",
              }}
            />
            <select
              value={realDimAxis}
              onChange={(e) => setRealDimAxis(e.target.value)}
              style={{
                background: "#0f1116",
                color: "#e8e8e8",
                border: "1px solid #2a2d35",
                borderRadius: "8px",
                padding: "0.6rem",
              }}
            >
              <option value="length">longueur (plus grande)</option>
              <option value="width">largeur (X)</option>
              <option value="depth">profondeur (Y)</option>
            </select>
          </div>
          <p style={{ color: "#6b7280", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            Mesure une dimension de l'objet au réglet et saisis-la : l'échelle
            est recalée dessus (taille exacte garantie). Si vide, l'échelle vient
            de la pièce de 1 €.
          </p>
        </div>

        <div>
          <label style={{ display: "block", marginBottom: "0.5rem" }}>
            3. Consigne vocale
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

        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <input
            type="checkbox"
            checked={quality}
            onChange={(e) => setQuality(e.target.checked)}
          />
          <span>
            Passe de qualité (meilleur rendu, ~2× plus lent)
          </span>
        </label>

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

      {result && result.metric && (
        <section style={{ marginTop: "1.5rem" }}>
          <h2 style={{ fontSize: "1.2rem" }}>Résultat</h2>
          <p style={{ color: "#9aa0aa" }}>
            Transcription : « {result.transcript} » — {result.metric.width_mm} ×{" "}
            {result.metric.depth_mm} mm (long. {result.metric.length_mm} mm,
            calibr. {result.metric.calibration}) — tentatives : {result.attempts}
          </p>
          <CodeEditor
            initialCode={result.scad_code}
            initialStlUrl={result.stl_url ? apiUrl(result.stl_url) : null}
            initialPartsUrl={result.parts_url ? apiUrl(result.parts_url) : null}
          />
        </section>
      )}
    </main>
  );
}
