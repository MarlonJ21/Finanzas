"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Cell } from "recharts";
import { api, money, pct, API_BASE, type DataStatus, type PlannerCategory, type PlannerDetail, type PlannerSummary } from "../../lib/api";

const scenarios = ["CURRENT", "REALISTIC", "AGGRESSIVE"] as const;

export default function PlannerPage() {
  const [scenario, setScenario] = useState<(typeof scenarios)[number]>("REALISTIC");
  const [selected, setSelected] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["data-status"], queryFn: () => api<DataStatus>("/data/status") });
  const summary = useQuery({ queryKey: ["planner-summary", scenario], queryFn: () => api<PlannerSummary>(`/planner/summary?scenario=${scenario}`) });
  const rows = useQuery({ queryKey: ["planner-categories", scenario], queryFn: () => api<PlannerCategory[]>(`/planner/categories?scenario=${scenario}`) });
  const detail = useQuery({ queryKey: ["planner-detail", scenario, selected], queryFn: () => api<PlannerDetail>(`/planner/categories/${selected}?scenario=${scenario}`), enabled: !!selected });

  const planMonthName = summary.data?.plan_month
    ? (() => {
        const d = new Date(summary.data.plan_month + "T00:00:00");
        return d.toLocaleDateString("es-VE", { month: "long" });
      })()
    : "el próximo mes";

  const chartData = useMemo(() => [...(rows.data ?? [])].map((row) => ({ name: row.subcategory, delta: Number((row.suggested_budget - row.current_budget).toFixed(2)) })).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 8), [rows.data]);
  const selectedRow = rows.data?.find((row) => row.id_category === selected);

  return (
    <section className="page">
      <div className="surface panel-pad page">
        <div className="planner-title-row">
          <div>
            <p className="eyebrow">Planificador Proximo Mes</p>
            <h1>Planifica con base en consumo, historico y escenario de ahorro.</h1>
          </div>
          <div className="planner-meta">
            <span className="context-pill">Mes plan {summary.data?.plan_month?.slice(0, 7) ?? "-"}</span>
            <span className="context-pill">Escenario {scenario}</span>
            <span className="context-pill">Estado {summary.data?.state ?? "-"}</span>
            <span className="context-pill">Fecha corte {status.data?.cut_date ?? "-"}</span>
          </div>
        </div>
        <div className="segmented">
          {scenarios.map((item) => <button className={`segment ${scenario === item ? "active" : ""}`} key={item} onClick={() => setScenario(item)}>{item}</button>)}
        </div>
        {summary.data ? (
          <div className="planner-kpis">
            <Kpi label="Presupuesto actual" value={money(summary.data.current_budget)} />
            <Kpi label="Forecast" value={money(summary.data.forecast)} accent="cyan" />
            <Kpi label="Sugerido" value={money(summary.data.suggested)} accent="violet" />
            <Kpi label="Final" value={money(summary.data.final)} />
            <Kpi label="Ahorro esperado" value={money(summary.data.expected_saving)} accent="green" note={pct(summary.data.expected_saving_pct)} />
          </div>
        ) : <div className="skeleton" />}
        {summary.data ? (
          <div className="surface-lite model-strip">
            <strong>Para {planMonthName} el modelo recomienda {money(summary.data.final)}.</strong>
            <span className="subtle">Son {money(Math.abs(summary.data.forecast - summary.data.final))} {summary.data.final <= summary.data.forecast ? "menos" : "mas"} que continuar con tu comportamiento proyectado.</span>
            <strong className="green">Ahorro esperado: {money(summary.data.expected_saving)} · {pct(summary.data.expected_saving_pct)}</strong>
          </div>
        ) : null}
      </div>

      <div className="planner-workspace">
        <div className="surface panel-pad">
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Categoria</th><th className="right">Actual</th><th className="right">MTD</th><th className="right">Proy. cierre</th><th className="right">Forecast</th><th className="right">Sugerido</th><th className="right">Manual</th><th className="right">Final</th><th>Confianza</th></tr></thead>
              <tbody>
                {(rows.data ?? []).map((row) => (
                  <tr className={selected === row.id_category ? "selected" : ""} key={row.id_category} onClick={() => setSelected(row.id_category)}>
                    <td><strong>{row.category}</strong><div className="subtle">{row.subcategory}</div></td>
                    <td className="right">{money(row.current_budget)}</td>
                    <td className="right">{money(row.current_mtd)}</td>
                    <td className="right">{money(row.projected_close)}</td>
                    <td className="right cyan">{money(row.forecast_next_month)}</td>
                    <td className="right violet">{money(row.suggested_budget)}</td>
                    <td className="right">{row.manual_budget == null ? "-" : money(row.manual_budget)}</td>
                    <td className="right"><strong>{money(row.final_budget)}</strong></td>
                    <td><Confidence value={row.confidence} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <Inspector detail={detail.data} selectedRow={selectedRow} summary={summary.data} scenario={scenario} onSaved={() => { queryClient.invalidateQueries({ queryKey: ["planner-summary"] }); queryClient.invalidateQueries({ queryKey: ["planner-categories"] }); queryClient.invalidateQueries({ queryKey: ["planner-detail"] }); }} />
      </div>

      <div className="content-grid">
        <div className="surface panel-pad">
          <h2>Donde cambia tu presupuesto</h2>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={chartData} layout="vertical" margin={{ left: 40, right: 28 }}>
                <XAxis type="number" stroke="#aeb9d0" />
                <YAxis dataKey="name" type="category" stroke="#aeb9d0" width={120} />
                <Bar dataKey="delta" radius={[6, 6, 6, 6]}>
                  {chartData.map((entry) => <Cell key={entry.name} fill={entry.delta <= 0 ? "#33E6A4" : "#FF5E67"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="surface panel-pad">
          <h2>Confianza del modelo</h2>
          <div className="detail-grid">
            <Kpi label="Alta" value={String(summary.data?.confidence_high ?? 0)} accent="green" />
            <Kpi label="Media" value={String(summary.data?.confidence_medium ?? 0)} accent="yellow" />
            <Kpi label="Baja" value={String(summary.data?.confidence_low ?? 0)} accent="red" />
          </div>
        </div>
      </div>
    </section>
  );
}

function Inspector({ detail, selectedRow, summary, scenario, onSaved }: { detail?: PlannerDetail; selectedRow?: PlannerCategory; summary?: PlannerSummary; scenario: string; onSaved: () => void }) {
  const [draft, setDraft] = useState<string>("");
  const [dirty, setDirty] = useState(false);
  const mutation = useMutation({
    mutationFn: async () => {
      if (!detail || !summary) return null;
      const res = await fetch(`${API_BASE}/planner/overrides/${detail.id_category}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_month: summary.plan_month, scenario, manual_budget_usd: Number(draft) })
      });
      if (!res.ok) throw new Error("OVERRIDE_FAILED");
      return res.json();
    },
    onSuccess: () => { setDirty(false); onSaved(); }
  });

  if (!selectedRow) return <aside className="surface panel-pad inspector empty-state"><div><h2>Selecciona una categoria</h2><p>para entender la recomendacion y ajustar tu presupuesto.</p></div></aside>;
  const data = detail ?? selectedRow;
  const finalBudgetVal = Number(data.final_budget ?? (data as any).final ?? data.suggested_budget ?? (data as any).suggested ?? 0);
  const manualBudgetVal = data.manual_budget ?? (data as any).manual;
  const draftValue = dirty ? Number(draft || 0) : Number(manualBudgetVal ?? finalBudgetVal);
  const simulatedFinal = summary ? summary.final - finalBudgetVal + draftValue : 0;
  const simulatedSaving = summary ? summary.expected_saving + finalBudgetVal - draftValue : 0;
  const savingPct = summary?.expected_saving && summary.expected_saving_pct ? simulatedSaving / (summary.expected_saving / summary.expected_saving_pct) : 0;

  return (
    <aside className="surface panel-pad inspector">
      <div>
        <h2>{data.category}</h2>
        <p className="subtle">{data.subcategory}</p>
      </div>
      <div className="button-row">
        <span className="status-chip status-muted">{data.forecast_type}</span>
        <Confidence value={data.confidence} />
        <span className="status-chip status-muted">{data.flexibility}</span>
        <span className="status-chip status-muted">{data.is_essential ? "Esencial" : "Flexible"}</span>
      </div>
      <div className="detail-grid">
        <Small label="Actual" value={money(data.current_budget)} />
        <Small label="MTD" value={money(data.current_mtd)} />
        <Small label="Mismo periodo anterior" value={money(data.previous_same_period)} />
        <Small label="Proyeccion cierre" value={money(data.projected_close)} />
        <Small label="Forecast" value={money(data.forecast_next_month)} />
        <Small label="Sugerido" value={money(data.suggested_budget ?? (data as any).suggested)} />
        <Small label="Manual" value={manualBudgetVal == null ? "-" : money(manualBudgetVal)} />
        <Small label="Final" value={money(finalBudgetVal)} />
      </div>
      <div className="surface-lite panel-pad">
        <h2>¿Por que este monto?</h2>
        <p className="subtle">{detail?.confidence_reason || `El predictor usa el comportamiento reciente y clasifica esta categoria como ${data.forecast_type.toLowerCase()} con confianza ${data.confidence.toLowerCase()}.`}</p>
      </div>
      <div>
        <label className="metric-label">Presupuesto manual</label>
        <input className="number-input" type="number" min="0" value={dirty ? draft : manualBudgetVal ?? finalBudgetVal} onChange={(event) => { setDraft(event.target.value); setDirty(true); }} />
      </div>
      {dirty ? <div className="surface-lite panel-pad"><strong className="yellow">Cambios sin guardar</strong><p className="subtle">Nuevo presupuesto mensual: {money(simulatedFinal)}. Ahorro esperado: {money(simulatedSaving)} · {pct(savingPct)}</p></div> : null}
      {mutation.isSuccess && !dirty ? <strong className="green">Ajuste guardado</strong> : null}
      <div className="button-row">
        <button className="secondary-button" disabled={!dirty} onClick={() => { setDirty(false); setDraft(""); }}>Cancelar</button>
        <button className="primary-button" disabled={!dirty || mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? "Guardando" : "Guardar ajuste"}</button>
      </div>
    </aside>
  );
}

function Kpi({ label, value, accent, note }: { label: string; value: string; accent?: string; note?: string }) {
  return <div className="metric-tile"><div className="metric-label">{label}</div><div className={`metric-value ${accent ?? ""}`}>{value}</div>{note ? <div className="metric-note">{note}</div> : null}</div>;
}

function Small({ label, value }: { label: string; value: string }) {
  return <div className="detail-cell"><div className="metric-label">{label}</div><strong>{value}</strong></div>;
}

function Confidence({ value }: { value: string }) {
  const cls = value === "HIGH" ? "conf-high" : value === "MEDIUM" ? "conf-medium" : "conf-low";
  return <span className={`confidence-chip ${cls}`}>{value}</span>;
}
