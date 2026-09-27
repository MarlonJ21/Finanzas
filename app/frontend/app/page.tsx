"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { api, money, pct, type Category, type DashboardSummary, type DataStatus } from "../lib/api";

export default function HomePage() {
  const status = useQuery({ queryKey: ["data-status"], queryFn: () => api<DataStatus>("/data/status") });
  const currentMonth = status.data?.current_month?.slice(0, 7);
  const summary = useQuery({
    queryKey: ["dashboard-summary", currentMonth],
    queryFn: () => api<DashboardSummary>(currentMonth ? `/dashboard/summary?month=${currentMonth}&scenario=REALISTIC` : "/dashboard/summary?scenario=REALISTIC"),
    enabled: !status.isLoading,
  });
  const categories = useQuery({
    queryKey: ["dashboard-categories", currentMonth],
    queryFn: () => api<Category[]>(currentMonth ? `/dashboard/categories?month=${currentMonth}&scenario=REALISTIC` : "/dashboard/categories?scenario=REALISTIC"),
    enabled: !status.isLoading,
  });

  if (status.isLoading || summary.isLoading || categories.isLoading) return <div className="page"><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>;
  if (!summary.data || !categories.data) throw new Error("HOME_DATA_ERROR");

  const monthLabel = status.data?.current_month
    ? (() => {
        const d = new Date(status.data.current_month + "T00:00:00");
        const formatted = d.toLocaleDateString("es-VE", { month: "long", year: "numeric" });
        return formatted.charAt(0).toUpperCase() + formatted.slice(1);
      })()
    : "Mes actual";

  const consumed = summary.data.monthly_consumed_pct;
  const qExcess = Math.max(summary.data.biweekly_spend - summary.data.biweekly_budget, 0);
  const exceeded = categories.data.filter((row) => row.status === "EXCEEDED");
  const noBudget = categories.data.filter((row) => row.status === "NO_BUDGET");
  const alerts = [
    ...exceeded.slice(0, 3).map((row) => `${row.category} excede el presupuesto por ${money(Math.abs(row.available))}.`),
    ...noBudget.slice(0, 2).map((row) => `${row.category} tiene gasto sin presupuesto.`),
    ...(qExcess > 0 ? [`La quincena esta excedida por ${money(qExcess)}.`] : []),
    ...(status.data?.pending_classification ? [`${status.data.pending_classification} movimientos pendientes de clasificacion.`] : [])
  ];
  const topCategories = [...categories.data].sort((a, b) => b.spent - a.spent).slice(0, 8);

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">{monthLabel}</p>
          <h1>Estado financiero del mes</h1>
          <p className="subtle">Tu resumen diario con presupuesto, gasto, quincena y alertas reales.</p>
        </div>
      </div>

      <div className="surface hero-finance">
        <div className="hero-grid">
          <Metric label="Presupuesto" value={money(summary.data.monthly_budget)} />
          <Metric label="Gastado" value={money(summary.data.personal_spend)} accent="cyan" />
          <Metric label="Disponible" value={money(summary.data.monthly_available)} />
          <Metric label="Consumido" value={pct(consumed)} accent={consumed >= 1 ? "red" : consumed >= .8 ? "yellow" : "green"} />
          <Metric label="Safe to Spend" value={money(summary.data.safe_to_spend)} accent={summary.data.safe_to_spend > 0 ? "green" : "yellow"} note="Disponible seguro para gastar en la quincena." />
        </div>
        <div className="progress-block">
          <div>
            <h2>Progreso del mes</h2>
            <p className="subtle">Gastado {money(summary.data.personal_spend)} de {money(summary.data.monthly_budget)}</p>
          </div>
          <div className="progress-track"><div className="progress-fill" style={{ width: `${Math.max(0, Math.min(consumed * 100, 100))}%` }} /></div>
          <strong>{pct(consumed)}</strong>
        </div>
      </div>

      <div className="content-grid">
        <div className="surface panel-pad">
          <h2>¿Dónde se está yendo tu dinero?</h2>
          <div className="category-list">
            {topCategories.map((row) => (
              <div className="category-row" key={`${row.category}-${row.subcategory}`}>
                <div><strong>{row.category}</strong><div className="subtle">{row.subcategory}</div></div>
                <div><strong>{money(row.spent)}</strong><div className="subtle">de {money(row.budget)}</div></div>
                <div className="progress-track"><div className="progress-fill" style={{ width: `${Math.max(0, Math.min(row.consumed_pct * 100, 100))}%` }} /></div>
                <StatusChip status={row.status} />
              </div>
            ))}
          </div>
        </div>

        <aside className="page">
          <div className="surface panel-pad">
            <h2>Esta quincena</h2>
            <div className="detail-grid">
              <Metric label="Presupuesto Q" value={money(summary.data.biweekly_budget)} />
              <Metric label="Gastado Q" value={money(summary.data.biweekly_spend)} accent={qExcess > 0 ? "red" : "cyan"} />
              <Metric label="Disponible Q" value={money(summary.data.biweekly_available)} accent={summary.data.biweekly_available < 0 ? "red" : "green"} />
              <Metric label="Salario cobrado" value={money(summary.data.salary_collected_biweekly)} />
            </div>
            {qExcess > 0 ? <p className="red" style={{ marginTop: 14 }}><strong>Exceso {money(qExcess)}</strong></p> : null}
          </div>

          {alerts.length ? (
            <div className="surface panel-pad">
              <h2><AlertTriangle size={18} /> Atencion</h2>
              <div className="alert-list">{alerts.map((alert) => <div className="alert-item" key={alert}>{alert}</div>)}</div>
            </div>
          ) : (
            <div className="surface panel-pad empty-state"><div><h2>Sin alertas</h2><p>Todo lo importante esta bajo control.</p></div></div>
          )}
        </aside>
      </div>
    </section>
  );
}

function Metric({ label, value, accent, note }: { label: string; value: string; accent?: string; note?: string }) {
  return <div className="metric-tile"><div className="metric-label">{label}</div><div className={`metric-value ${accent ?? ""}`}>{value}</div>{note ? <div className="metric-note">{note}</div> : null}</div>;
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, [string, string]> = {
    WITHIN: ["Dentro", "status-within"],
    NEAR_LIMIT: ["Cerca", "status-near"],
    EXCEEDED: ["Excede", "status-exceeded"],
    NO_BUDGET: ["Sin presupuesto", "status-exceeded"],
    NO_ACTIVITY: ["Sin actividad", "status-muted"]
  };
  const [label, cls] = map[status] ?? [status, "status-muted"];
  return <span className={`status-chip ${cls}`}>{label}</span>;
}
