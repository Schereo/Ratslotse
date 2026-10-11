"use client";

import { useEffect } from "react";
import { meldeFehler } from "@/lib/fehler-melden";
import { chunkFehlerHeilen } from "@/lib/chunk-fehler";

/** Die letzte Grenze: Ein Fehler im Wurzel-Layout oder in den Providern.
 *
 *  Ohne diese Datei zeigte Next dafür seine eigene weiße Seite („Application
 *  error: a client-side exception has occurred") — ohne Marke, ohne Ausweg,
 *  und ohne dass wir davon erfuhren. Sie ersetzt das Wurzel-Layout, also auch
 *  dessen Stylesheet: deshalb Inline-Stile und keine Bausteine, die auf
 *  Theme oder Provider angewiesen sind. */
export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    console.error(error);
    if (chunkFehlerHeilen(error)) return;
    meldeFehler(error.digest ? Object.assign(error, {
      message: `${error.message} [digest ${error.digest}]`,
    }) : error);
  }, [error]);

  return (
    <html lang="de">
      <body style={{
        margin: 0, minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
        background: "#f6f9fb", color: "#0d1b2b", padding: "16px",
        fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif",
      }}>
        <div style={{ maxWidth: 380, textAlign: "center", background: "#fff", borderRadius: 16, padding: "32px 24px", border: "1px solid #e2e8f0" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/lotti/kopf.png" alt="" width={96} height={96} style={{ margin: "0 auto" }}
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }} />
          <h1 style={{ fontSize: 18, fontWeight: 600, margin: "16px 0 8px" }}>Ratslotse ist gerade gestolpert</h1>
          <p style={{ fontSize: 14, lineHeight: 1.5, color: "#475569", margin: 0 }}>
            Wir haben den Fehler mitbekommen. Meist hilft es, die Seite neu zu laden.
          </p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 20, flexWrap: "wrap" }}>
            <button type="button" onClick={() => window.location.reload()}
              style={{ background: "#0764a6", color: "#fff", border: 0, borderRadius: 10, padding: "10px 16px", fontSize: 14, fontWeight: 600, cursor: "pointer" }}>
              Seite neu laden
            </button>
            <a href="/" style={{ color: "#0764a6", padding: "10px 16px", fontSize: 14, fontWeight: 600, textDecoration: "none" }}>
              Zur Startseite
            </a>
          </div>
        </div>
      </body>
    </html>
  );
}
