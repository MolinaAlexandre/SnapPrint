import type { ReactNode } from "react";

export const metadata = {
  title: "SnapPrint / VoiceCAD",
  description: "Photo + voix -> modèle 3D imprimable",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr">
      <body
        style={{
          margin: 0,
          fontFamily:
            "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
          background: "#0b0c10",
          color: "#e8e8e8",
        }}
      >
        {children}
      </body>
    </html>
  );
}
