"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Bot, CalendarDays, CheckCircle2, Home, Landmark, Loader2, RefreshCw, ShoppingBag, SlidersHorizontal, Table2, Upload, WalletCards, X } from "lucide-react";
import { useState } from "react";
import { api, uploadRial, type DataStatus } from "../../lib/api";

const nav = [
  { href: "/", label: "Inicio", icon: Home },
  { href: "/planner", label: "Planificador", icon: BarChart3 },
  { href: "/premiados", label: "PremiadosVE", icon: ShoppingBag },
  { href: "/luka", label: "LUKA", icon: Bot },
  { href: "/movements", label: "Movimientos", icon: Table2 },
  { href: "/settings", label: "Clasificación y Reglas", icon: SlidersHorizontal },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const status = useQuery({ queryKey: ["data-status"], queryFn: () => api<DataStatus>("/data/status") });
  const lukaStatus = useQuery({ queryKey: ["luka-status"], queryFn: () => api<{ enabled: boolean }>("/luka/status"), retry: false });
  const visibleNav = nav.filter((item) => item.href !== "/luka" || lukaStatus.data?.enabled === true);

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
      <header className="mobile-header">
        <div className="mobile-brand">
          <span className="brand-mark"><Landmark size={18} /></span>
          <span>Finanzas</span>
        </div>
        <div className="mobile-header-actions">
          <span className="mobile-corte-pill">
            {status.data?.cut_date ? `Corte ${status.data.cut_date.slice(5)}` : "Corte -"}
          </span>
          <button className="mobile-sync-btn" onClick={() => setOpen(true)} title="Actualizar RIAL" aria-label="Actualizar RIAL">
            <Upload size={16} />
          </button>
        </div>
      </header>

      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><Landmark size={18} /></span>Finanzas</div>
        <nav className="nav-list">
          {visibleNav.map((item) => {
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

      <nav className="mobile-bottom-nav">
        {visibleNav.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          const isSettings = item.href === "/settings";
          const shortLabel = item.label.split(" ")[0];
          return (
            <Link className={`bottom-nav-item ${active ? "active" : ""}`} href={item.href} key={item.href}>
              <div className="bottom-nav-icon-wrap">
                <Icon size={20} />
                {isSettings && pendingCount > 0 ? (
                  <span className="nav-badge-dot">{pendingCount}</span>
                ) : null}
              </div>
              <span className="bottom-nav-label">{shortLabel}</span>
            </Link>
          );
        })}
      </nav>

      {open ? <RialModal onClose={() => setOpen(false)} /> : null}
    </div>
  );
}

const ETL_STEPS = [
  { id: 0, label: "Validación CSV", desc: "Comprobando columnas y estructura" },
  { id: 1, label: "Normalización", desc: "Mapeando cuentas, monedas y tasas" },
  { id: 2, label: "Clasificación", desc: "Asignando categorías nativas y dominios" },
  { id: 3, label: "Presupuesto", desc: "Consolidando cuotas, deudas y límites" },
  { id: 4, label: "Forecast", desc: "Calculando proyecciones y escenarios" },
  { id: 5, label: "Integridad", desc: "Verificando grano y guardando datos" },
];

function RialModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [activeStep, setActiveStep] = useState<number>(-1);
  const [progressPct, setProgressPct] = useState<number>(0);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFileSelected(selectedFile: File) {
    setFile(selectedFile);
    await startFullImport(selectedFile);
  }

  async function startFullImport(selectedFile: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    setActiveStep(0);
    setProgressPct(15);

    let current = 0;
    const interval = setInterval(() => {
      current += 1;
      if (current <= 4) {
        setActiveStep(current);
        setProgressPct(Math.min(20 + current * 16, 88));
      }
    }, 700);

    try {
      const response = await uploadRial("commit", selectedFile);
      clearInterval(interval);
      setActiveStep(5);
      setProgressPct(100);
      setResult(response);
      if (response.commit_status === "PASS") {
        await queryClient.invalidateQueries();
      } else if (response.errors && response.errors.length > 0) {
        setError(response.errors.join(". "));
      }
    } catch (err: any) {
      clearInterval(interval);
      setActiveStep(-1);
      setProgressPct(0);
      setError(err?.message || "Error al procesar y actualizar el archivo. Revisa que el backend esté disponible.");
    } finally {
      setBusy(false);
    }
  }

  const isSuccess = result?.commit_status === "PASS";

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="modal">
        <div className="sheet-handle" />
        <div className="modal-header">
          <div>
            <p className="eyebrow">Actualizar RIAL</p>
            <h1>Importa tu export financiero</h1>
            <p className="subtle">Sube tu archivo CSV y LUKA validará, clasificará y actualizará automáticamente tus finanzas.</p>
          </div>
          <button className="ghost-button" aria-label="Cerrar" disabled={busy} onClick={onClose}><X size={18} /></button>
        </div>
        <div className="panel-pad page">
          {!isSuccess ? (
            <label className={`dropzone ${busy ? "disabled-dropzone" : ""}`} style={{ pointerEvents: busy ? "none" : "auto", opacity: busy ? 0.7 : 1 }}>
              <input
                style={{ display: "none" }}
                type="file"
                accept=".csv"
                disabled={busy}
                onChange={(event) => {
                  const f = event.target.files?.[0];
                  if (f) handleFileSelected(f);
                }}
              />
              <span>
                <Upload size={28} />
                <h2>{file ? file.name : "Arrastra tu export de RIAL aquí"}</h2>
                <p className="subtle">o toca para seleccionar y actualizar automáticamente en un clic</p>
              </span>
            </label>
          ) : null}

          {/* Stepper animado y barra de progreso */}
          <div className="etl-stepper-box">
            {busy && (
              <>
                <div className="etl-progress-bar-wrap">
                  <div className="etl-progress-fill" style={{ width: `${progressPct}%` }} />
                </div>
                <div className="etl-phase-banner">
                  <div className="etl-phase-pulse" />
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <strong style={{ fontSize: 13, color: "var(--cyan)" }}>
                      {ETL_STEPS[Math.max(activeStep, 0)]?.label}
                    </strong>
                    <span style={{ fontSize: 11, color: "var(--muted)" }}>
                      {ETL_STEPS[Math.max(activeStep, 0)]?.desc}
                    </span>
                  </div>
                </div>
              </>
            )}

            <div className="step-list">
              {ETL_STEPS.map((s, index) => {
                const isDone = isSuccess || (busy && index < activeStep);
                const isCurrent = busy && index === activeStep;
                return (
                  <div
                    className={`step ${isDone ? "done" : isCurrent ? "current-running active" : ""}`}
                    key={s.id}
                  >
                    {isDone ? (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <CheckCircle2 size={13} style={{ color: "var(--green)" }} /> {s.label}
                      </span>
                    ) : isCurrent ? (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <Loader2 size={13} className="spin-animate" style={{ color: "var(--cyan)" }} /> {s.label}
                      </span>
                    ) : (
                      <span>○ {s.label}</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {result && isSuccess ? (
            <div className="surface-lite panel-pad">
              <h2 className="green" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <CheckCircle2 size={20} style={{ color: "var(--green)" }} /> ¡Actualización completada con éxito!
              </h2>
              <p className="subtle" style={{ marginTop: 4, marginBottom: 12 }}>
                Tus movimientos, reglas y presupuestos quedaron perfectamente sincronizados.
              </p>
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
              <div style={{ marginTop: 16, display: "flex", gap: 10 }}>
                <button className="primary-button" style={{ flex: 1 }} onClick={onClose}>
                  Ver resumen actualizado
                </button>
              </div>
            </div>
          ) : null}

          {error ? (
            <div className="surface-lite panel-pad" style={{ border: "1px solid rgba(255, 94, 103, 0.4)" }}>
              <div className="alert-item red">{error}</div>
              <button
                className="secondary-button"
                style={{ marginTop: 12 }}
                onClick={() => {
                  if (file) startFullImport(file);
                }}
              >
                Reintentar carga
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="detail-cell"><div className="metric-label">{label}</div><strong>{value}</strong></div>;
}
