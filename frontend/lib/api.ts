// Base des appels API.
//
// Les appels de génération/compilation peuvent durer ~1-2 min. Le proxy Next
// (rewrites) coupe les connexions trop longues (socket hang up). Si
// NEXT_PUBLIC_BACKEND_URL est défini, on appelle le backend EN DIRECT depuis le
// navigateur (le backend autorise CORS depuis localhost:3000), ce qui évite le
// timeout du proxy. Sinon on retombe sur le chemin relatif "/api" (proxy).
export const API_BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") ?? "";

export function apiUrl(path: string): string {
  // path commence par "/api/..."
  return `${API_BASE}${path}`;
}
