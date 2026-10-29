"use client";

import { useEffect, useState } from "react";
import ThreeViewer from "@/components/ThreeViewer";
import { apiUrl } from "@/lib/api";

type CompileResponse = {
  job_id: string;
  success: boolean;
  attempts: number;
  scad_code: string;
  errors: string[];
  stl_url: string | null;
};

type Props = {
  initialCode: string;
  initialStlUrl: string | null;
};

const box: React.CSSProperties = {
  width: "100%",
  background: "#0f1116",
  color: "#e8e8e8",
  border: "1px solid #2a2d35",
  borderRadius: "8px",
  padding: "0.6rem",
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
};

const btn = (disabled: boolean, bg = "#4f9dff"): React.CSSProperties => ({
  padding: "0.6rem 1.1rem",
  borderRadius: "8px",
  border: "none",
  cursor: disabled ? "default" : "pointer",
  background: disabled ? "#2a2d35" : bg,
  color: "white",
  fontWeight: 600,
});

export default function CodeEditor({ initialCode, initialStlUrl }: Props) {
  const [code, setCode] = useState(initialCode);
  const [stlUrl, setStlUrl] = useState<string | null>(initialStlUrl);
  const [aiRequest, setAiRequest] = useState("");
  const [busy, setBusy] = useState<null | "recompile" | "refine">(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [note, setNote] = useState<string | null>(null);

  // Si une nouvelle génération arrive du parent, on resynchronise.
  useEffect(() => {
    setCode(initialCode);
    setStlUrl(initialStlUrl);
    setErrors([]);
    setNote(null);
  }, [initialCode, initialStlUrl]);

  const apply = (data: CompileResponse, okMsg: string) => {
    setCode(data.scad_code);
    setErrors(data.errors || []);
    if (data.success && data.stl_url) {
      setStlUrl(apiUrl(data.stl_url));
      setNote(`${okMsg} (${data.attempts} passe${data.attempts > 1 ? "s" : ""}).`);
    } else {
      setNote("La compilation a échoué. Voir les erreurs ci-dessous.");
    }
  };

  const recompile = async () => {
    setBusy("recompile");
    setNote(null);
    try {
      const res = await fetch(apiUrl("/api/recompile"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scad_code: code }),
      });
      const data = await res.json();
      if (!data || !data.scad_code) {
        setNote(data?.detail || `Échec (HTTP ${res.status}).`);
        return;
      }
      apply(data as CompileResponse, "Recompilé");
    } catch (e) {
      setNote("Erreur réseau : " + (e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const refine = async () => {
    if (!aiRequest.trim()) {
      setNote("Décris la modification souhaitée.");
      return;
    }
    setBusy("refine");
    setNote(null);
    try {
      const res = await fetch(apiUrl("/api/refine"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scad_code: code, request: aiRequest.trim() }),
      });
      const data = await res.json();
      if (!data || !data.scad_code) {
        setNote(data?.detail || `Échec (HTTP ${res.status}).`);
        return;
      }
      apply(data as CompileResponse, "Modifié par l'IA");
      setAiRequest("");
    } catch (e) {
      setNote("Erreur réseau : " + (e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <ThreeViewer stlUrl={stlUrl} />
      {stlUrl && (
        <a href={stlUrl} download style={{ color: "#4f9dff" }}>
          ⬇️ Télécharger le STL
        </a>
      )}

      {/* Modifier par IA */}
      <div style={{ display: "grid", gap: "0.5rem" }}>
        <label style={{ fontWeight: 600 }}>✨ Modifier par IA</label>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            value={aiRequest}
            onChange={(e) => setAiRequest(e.target.value)}
            placeholder="ex : augmente la hauteur de 5 mm, arrondis plus les bords"
            style={{ ...box, flex: 1 }}
            disabled={busy !== null}
          />
          <button
            type="button"
            onClick={refine}
            disabled={busy !== null}
            style={btn(busy !== null, "#9b6dff")}
          >
            {busy === "refine" ? "Modification…" : "Appliquer"}
          </button>
        </div>
      </div>

      {/* Éditeur de code */}
      <div style={{ display: "grid", gap: "0.5rem" }}>
        <label style={{ fontWeight: 600 }}>Code OpenSCAD (éditable)</label>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          spellCheck={false}
          rows={16}
          style={{ ...box, fontSize: "0.8rem", lineHeight: 1.4, resize: "vertical" }}
          disabled={busy !== null}
        />
        <div>
          <button
            type="button"
            onClick={recompile}
            disabled={busy !== null}
            style={btn(busy !== null)}
          >
            {busy === "recompile" ? "Compilation…" : "🔁 Recompiler"}
          </button>
        </div>
      </div>

      {note && <p style={{ color: "#9aa0aa", margin: 0 }}>{note}</p>}

      {errors.length > 0 && (
        <details>
          <summary style={{ cursor: "pointer", color: "#ff9f6b" }}>
            Erreurs de compilation ({errors.length})
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
            {errors.join("\n\n")}
          </pre>
        </details>
      )}
    </div>
  );
}
