"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, CalendarDays, Home, Landmark, RefreshCw, SlidersHorizontal, Table2, Upload, WalletCards, X } from "lucide-react";
import { useState } from "react";
import { api, uploadRial, type DataStatus } from "../../lib/api";

const nav = [
  { href: "/", label: "Inicio", icon: Home },
  { href: "/planner", label: "Planificador", icon: BarChart3 },
  { href: "/movements", label: "Movimientos", icon: Table2 },
  { href: "/settings", label: "Clasificación y Reglas", icon: SlidersHorizontal },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const status = useQuery({ queryKey: ["data-status"], queryFn: () => api<DataStatus>("/data/status") });

  const monthName = status.data?.current_month
    ? (() => {
        const d = new Date(status.data.current_month + "T00:00:00");
        const formatted = d.toLocaleDateString("es-VE", { month: "long", year: "numeric" });
        return formatted.charAt(0).toUpperCase() + formatted.slice(1);
      })()
    : "Mes actual";

  const pendingCount = status.data?.pending_classification ?? 0;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><Landmark size={18} /></span>Finanzas</div>
        <nav className="nav-list">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            const isSettings = item.href === "/settings";
            return (
              <Link className={`nav-item ${active ? "active" : ""}`} href={item.href} key={item.href}>
                <Icon size={18} />
                <span>{item.label}</span>
                {isSettings && pendingCount > 0 ? (
                  <span style={{
                    marginLeft: "auto",
                    background: "#f59e0b",
                    color: "#000",
                    fontWeight: 700,
                    fontSize: "0.75rem",
                    padding: "2px 7px",
                    borderRadius: 9999
                  }}>
                    {pendingCount}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div>
            <strong>Datos</strong>
            <div>Actualizado {status.data?.last_update ? new Date(status.data.last_update).toLocaleString("es-VE") : "sin datos"}</div>
          </div>
          <button className="primary-button" onClick={() => setOpen(true)}><Upload size={16} />Actualizar RIAL</button>
        </div>
      </aside>
      <main className="shell-main">
        <div className="topbar">
          <div className="context-row">
            <span className="context-pill"><CalendarDays size={15} />{monthName}</span>
            <span className="context-pill">Corte {status.data?.cut_date ?? "-"}</span>
            <span className="context-pill"><WalletCards size={15} />{status.data?.movement_count ?? 0} movimientos</span>
          </div>
          <button className="primary-button" onClick={() => setOpen(true)}><RefreshCw size={16} />Actualizar RIAL</button>
        </div>
        {children}
      </main>
      {open ? <RialModal onClose={() => setOpen(false)} /> : null}
    </div>
  );
}

function RialModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<"preview" | "commit" | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(mode: "preview" | "commit") {
    if (!file) return;
    setBusy(mode);
    setError(null);
    try {
      const response = await uploadRial(mode, file);
      setResult(response);
      if (mode === "commit" && response.commit_status === "PASS") {
        await queryClient.invalidateQueries();
      }
    } catch {
      setError("Esta vista publicada es de solo lectura. Para importar RIAL, abre la app local con tu backend encendido.");
    } finally {
      setBusy(null);
    }
  }

  const status = result?.commit_status ?? result?.validation_status;
  const ready = status === "PASS";

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <div className="modal-header">
          <div>
            <p className="eyebrow">Actualizar RIAL</p>
            <h1>Importa tu export financiero</h1>
            <p className="subtle">Primero validamos el archivo. Tus datos se reemplazan solo despues de confirmar.</p>
          </div>
          <button className="ghost-button" aria-label="Cerrar" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="panel-pad page">
          <label className="dropzone">
            <input style={{ display: "none" }} type="file" accept=".csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <span>
              <Upload size={28} />
              <h2>{file ? file.name : "Arrastra tu export de RIAL aqui"}</h2>
              <p className="subtle">o selecciona un archivo CSV</p>
            </span>
          </label>
          <div className="step-list">
            {["Archivo validado", "Normalizacion", "Clasificacion", "Presupuesto", "Forecast", "Validacion"].map((step, index) => (
              <div className={`step ${result ? "done" : index === 0 && busy ? "active" : ""}`} key={step}>{result ? "✓" : index === 0 && busy ? "●" : "○"} {step}</div>
            ))}
          </div>
          {result ? (
            <div className="surface-lite panel-pad">
              <h2>{ready ? "LISTO PARA ACTUALIZAR" : "REVISAR"}</h2>
              <div className="detail-grid">
                <Metric label="Archivo" value={String(result.filename ?? file?.name ?? "-")} />
                <Metric label="Movimientos" value={String(result.transaction_rows ?? "-")} />
                <Metric label="Fecha corte" value={String(result.cut_date ?? "-")} />
                <Metric label="Duplicados" value={String(result.possible_duplicates ?? 0)} />
                <Metric label="FX faltante" value={String(result.missing_fx ?? 0)} />
                <Metric label="Pendientes" value={String(result.pending_classification ?? 0)} />
              </div>
              {Boolean(result.is_merged) ? (
                <div style={{ marginTop: 12, padding: "8px 12px", background: "rgba(234, 179, 8, 0.15)", borderRadius: 6, fontSize: "0.85rem", color: "#eab308" }}>
                  <strong>Fusión inteligente por fecha:</strong> Se conservaron {String(result.preserved_rows)} movimientos anteriores y se actualizaron {String(result.incoming_rows)} movimientos de este archivo ({String(result.incoming_period ?? "")}).
                </div>
              ) : null}
              {Number(result.pending_classification ?? 0) > 0 ? (
                <div style={{ marginTop: 8, padding: "8px 12px", background: "rgba(59, 130, 246, 0.15)", borderRadius: 6, fontSize: "0.85rem", color: "#60a5fa" }}>
                  <strong>{String(result.pending_classification)} movimientos sin clasificar:</strong> Podrás revisarlos y crear reglas automáticas en la pestaña <em>Clasificación y Reglas</em>.
                </div>
              ) : null}
            </div>
          ) : null}
          {error ? <div className="alert-item red">{error}</div> : null}
          {result?.commit_status === "PASS" ? (
            <div className="surface-lite panel-pad">
              <h2 className="green">Actualizacion completada</h2>
              <p className="subtle">Movimientos, presupuesto, forecast y overrides preservados quedaron recalculados.</p>
              <button className="primary-button" onClick={onClose}>Ver resumen actualizado</button>
            </div>
          ) : (
            <div className="button-row">
              <button className="secondary-button" disabled={!file || !!busy} onClick={() => run("preview")}>{busy === "preview" ? "Validando" : "Preview"}</button>
              <button className="primary-button" disabled={!file || !!busy || !ready} onClick={() => run("commit")}>{busy === "commit" ? "Actualizando" : "Actualizar mis finanzas"}</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="detail-cell"><div className="metric-label">{label}</div><strong>{value}</strong></div>;
}
