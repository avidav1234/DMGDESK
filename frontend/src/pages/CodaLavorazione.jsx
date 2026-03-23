import { useState, useEffect, useCallback } from "react";

// ── Colori stati pallet ──────────────────────────────────────────
const STATI = {
  "IN LAVORAZIONE": { bg: "#0d2d5e", fg: "#fff",     border: "#1a4080" },
  "GREZZO":         { bg: "#fefce8", fg: "#854d0e",  border: "#eab308" },
  "FINITO":         { bg: "#dcfce7", fg: "#14532d",  border: "#22c55e" },
  "VUOTO":          { bg: "#f1f5f9", fg: "#94a3b8",  border: "#e2e8f0" },
  "GUASTO":         { bg: "#fef2f2", fg: "#991b1b",  border: "#f87171" },
};
const STATI_ORDER = ["VUOTO", "GREZZO", "FINITO", "GUASTO"];

// Estrae commessa/posizione/fase dal path NC
function parseProgram(path) {
  if (!path) return null;
  // Es: /_N_WKS_DIR/_N_4349_0221_WPD/_N_4349_0221_03_010_MPF
  const m = path.match(/_N_(\d+)_(\d+)_WPD\/_N_\d+_\d+_(.+?)_MPF/);
  if (m) return { commessa: m[1], posizione: m[2], fase: m[3] };
  // Fallback: solo nome file
  const m2 = path.match(/_N_([^/]+?)_(?:MPF|SPF)$/);
  return m2 ? { fase: m2[1] } : null;
}

const REFRESH_MS = 5000;

export default function CodaLavorazione() {
  const [pallets, setPallets] = useState(
    Array.from({ length: 6 }, (_, i) => ({ id: i + 1, stato: "VUOTO", programma: null }))
  );
  const [macchina, setMacchina]     = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError]           = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [rPallets, rMacchina] = await Promise.all([
        fetch("/api/pallet/"),
        fetch("/api/macchina-live/stato"),
      ]);

      const palletData  = rPallets.ok  ? await rPallets.json()  : null;
      const macchinaData = rMacchina.ok ? await rMacchina.json() : null;

      setMacchina(macchinaData);

      setPallets(prev => prev.map(p => {
        const saved = palletData?.[p.id] || {};
        let stato = saved.stato || "VUOTO";

        // Sovrascrive con IN LAVORAZIONE se macchina lo conferma
        if (
          macchinaData?.palletAttivo === p.id &&
          macchinaData?.progStatus === 3
        ) {
          stato = "IN LAVORAZIONE";
        }

        return { ...p, stato, programma: saved.programma || null };
      }));

      setLastUpdate(new Date().toLocaleTimeString("it-IT"));
      setError(null);
    } catch {
      setError("Errore connessione");
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, REFRESH_MS);
    return () => clearInterval(t);
  }, [fetchAll]);

  const setPalletStato = async (id, stato) => {
    if (stato === "IN LAVORAZIONE") return; // gestito automaticamente
    try {
      await fetch(`/api/pallet/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stato }),
      });
      await fetchAll();
    } catch {
      setError("Errore aggiornamento");
    }
  };

  const inLavorazione = macchina?.stato_programma === 3;
  const prog          = parseProgram(macchina?.programma_attivo);
  const utensile      = macchina?.utensile_attivo || null;
  const tNum          = macchina?.numero_utensile   || null;
  const alarm         = macchina?.allarme?.replace(/^\|[^|]*\|[^|]*\| ?/, "") || null;

  return (
    <div style={{
      display: "flex",
      gap: 20,
      padding: 20,
      height: "100%",
      boxSizing: "border-box",
      background: "var(--bg-base, #eef2f7)",
    }}>

      {/* ── Griglia 2×3 pallet ─────────────────────────────────── */}
      <div style={{ flexShrink: 0 }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 10,
        }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#0d2d5e", letterSpacing: 1 }}>
            PALLET
          </span>
          {lastUpdate && (
            <span style={{ fontSize: 10, color: "#94a3b8" }}>{lastUpdate}</span>
          )}
        </div>

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 155px)",
          gridTemplateRows: "repeat(3, 115px)",
          gap: 10,
        }}>
          {pallets.map(p => {
            const s        = STATI[p.stato] || STATI["VUOTO"];
            const isActive = macchina?.pallet_attivo === p.id;
            const isLav    = p.stato === "IN LAVORAZIONE";

            return (
              <div
                key={p.id}
                title={isLav ? "Gestito automaticamente dalla macchina" : "Click per cambiare stato"}
                style={{
                  background:   s.bg,
                  border:       `2px solid ${isActive ? "#f59e0b" : s.border}`,
                  borderRadius: 10,
                  padding:      "10px 12px",
                  cursor:       isLav ? "default" : "pointer",
                  position:     "relative",
                  boxShadow:    isActive
                    ? "0 0 0 3px rgba(245,158,11,0.25), 0 2px 6px rgba(0,0,0,0.12)"
                    : "0 1px 3px rgba(0,0,0,0.07)",
                  display:        "flex",
                  flexDirection:  "column",
                  justifyContent: "space-between",
                  transition: "box-shadow 0.2s",
                  userSelect: "none",
                }}
                onClick={() => {
                  if (isLav) return;
                  const idx  = STATI_ORDER.indexOf(p.stato);
                  const next = STATI_ORDER[(idx + 1) % STATI_ORDER.length];
                  setPalletStato(p.id, next);
                }}
              >
                {/* Numero + indicatore pulsante */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <span style={{ fontSize: 24, fontWeight: 900, color: s.fg, lineHeight: 1 }}>
                    P{p.id}
                  </span>
                  {isActive && (
                    <span style={{
                      width: 9, height: 9,
                      borderRadius: "50%",
                      background: "#f59e0b",
                      display: "inline-block",
                      animation: "blink 1.4s infinite",
                    }} />
                  )}
                </div>

                {/* Stato + programma */}
                <div>
                  <div style={{
                    fontSize: 9,
                    fontWeight: 700,
                    color: s.fg,
                    opacity: 0.9,
                    letterSpacing: 1,
                    textTransform: "uppercase",
                  }}>
                    {p.stato}
                  </div>
                  {p.programma && (
                    <div style={{
                      fontSize: 9,
                      color: s.fg,
                      opacity: 0.55,
                      marginTop: 2,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}>
                      {p.programma}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <style>{`
          @keyframes blink {
            0%, 100% { opacity: 1; }
            50%       { opacity: 0.3; }
          }
        `}</style>
      </div>

      {/* ── Pannello destro ─────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>

        {/* Stato macchina */}
        <div style={{
          background:   inLavorazione ? "#0d2d5e" : "#f8fafc",
          border:       `1px solid ${inLavorazione ? "#1a4080" : "#e2e8f0"}`,
          borderRadius: 12,
          padding:      "14px 18px",
          display:      "flex",
          alignItems:   "center",
          gap:          12,
        }}>
          <div style={{
            width:     11,
            height:    11,
            borderRadius: "50%",
            flexShrink:   0,
            background:   inLavorazione ? "#22c55e" : "#94a3b8",
            boxShadow:    inLavorazione ? "0 0 6px #22c55e" : "none",
          }} />
          <div>
            <div style={{
              fontSize:   13,
              fontWeight: 700,
              color:      inLavorazione ? "#ffffff" : "#374151",
            }}>
              {inLavorazione ? "IN LAVORAZIONE" : "FERMA"}
            </div>
            {macchina?.pallet_attivo > 0 && (
              <div style={{
                fontSize: 10,
                color:    inLavorazione ? "#93c5fd" : "#94a3b8",
                marginTop: 2,
              }}>
                Pallet {macchina.palletAttivo} in macchina
              </div>
            )}
          </div>
        </div>

        {/* Programma in esecuzione */}
        <div style={{
          background:   "#ffffff",
          border:       "1px solid #e2e8f0",
          borderRadius: 12,
          padding:      "14px 18px",
          flex:         "0 0 auto",
        }}>
          <div style={{ fontSize: 10, color: "#94a3b8", letterSpacing: 1, marginBottom: 8 }}>
            PROGRAMMA
          </div>
          {prog ? (
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
              {prog.commessa && (
                <div>
                  <div style={{ fontSize: 9, color: "#94a3b8" }}>COMMESSA</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: "#0d2d5e" }}>{prog.commessa}</div>
                </div>
              )}
              {prog.posizione && (
                <div>
                  <div style={{ fontSize: 9, color: "#94a3b8" }}>POSIZIONE</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: "#0d2d5e" }}>{prog.posizione}</div>
                </div>
              )}
              {prog.fase && (
                <div>
                  <div style={{ fontSize: 9, color: "#94a3b8" }}>FASE</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#475569" }}>{prog.fase}</div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ fontSize: 12, color: "#94a3b8" }}>—</div>
          )}
        </div>

        {/* Utensile attivo */}
        <div style={{
          background:   "#ffffff",
          border:       "1px solid #e2e8f0",
          borderRadius: 12,
          padding:      "14px 18px",
        }}>
          <div style={{ fontSize: 10, color: "#94a3b8", letterSpacing: 1, marginBottom: 6 }}>
            UTENSILE ATTIVO
          </div>
          {utensile ? (
            <div>
              <div style={{ fontSize: 17, fontWeight: 700, color: "#0d2d5e" }}>{utensile}</div>
              {tNum > 0 && (
                <div style={{ fontSize: 10, color: "#64748b", marginTop: 2 }}>T{tNum}</div>
              )}
            </div>
          ) : (
            <div style={{ fontSize: 12, color: "#94a3b8" }}>—</div>
          )}
        </div>

        {/* Allarmi */}
        {alarm && (
          <div style={{
            background:   "#fef2f2",
            border:       "1px solid #fca5a5",
            borderRadius: 12,
            padding:      "12px 16px",
          }}>
            <div style={{ fontSize: 10, color: "#991b1b", letterSpacing: 1, marginBottom: 4 }}>
              ALLARME
            </div>
            <div style={{ fontSize: 11, color: "#991b1b" }}>{alarm}</div>
          </div>
        )}

        {/* Errore connessione */}
        {error && (
          <div style={{
            background:   "#fef3c7",
            border:       "1px solid #fcd34d",
            borderRadius: 8,
            padding:      "8px 12px",
            fontSize:     11,
            color:        "#92400e",
          }}>
            ⚠️ {error}
          </div>
        )}

      </div>
    </div>
  );
}