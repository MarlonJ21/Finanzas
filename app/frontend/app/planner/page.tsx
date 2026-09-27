"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SlidersHorizontal, Sparkles, TrendingUp, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Cell } from "recharts";
import { api, money, pct, API_BASE, type DataStatus, type PlannerCategory, type PlannerDetail, type PlannerSummary } from "../../lib/api";

const scenarios = ["CURRENT", "REALISTIC", "AGGRESSIVE"] as const;

export default function PlannerPage() {
  const [scenario, setScenario] = useState<(typeof scenarios)[number]>("REALISTIC");
  const [selected, setSelected] = useState<string | null>(null);
  const [mobileModalOpen, setMobileModalOpen] = useState(false);

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

  const chartData = useMemo(
    () =>
      [...(rows.data ?? [])]
        .map((row) => ({ name: row.subcategory, delta: Number((row.suggested_budget - row.current_budget).toFixed(2)) }))
        .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
        .slice(0, 8),
    [rows.data]
  );

  const selectedRow = rows.data?.find((row) => row.id_category === selected);

  function handleSelectMobile(id: string) {
    setSelected(id);
    setMobileModalOpen(true);
  }

  return (
    <section className="page">
      <div className="surface panel-pad page">
        <div className="planner-title-row">
          <div>
            <p className="eyebrow">Planificador Próximo Mes</p>
            <h1>Planifica tu presupuesto futuro</h1>
            <p className="subtle">Proyecciones inteligentes basadas en tu historial y escenarios de ahorro.</p>
          </div>
          <div className="planner-meta">
            <span className="context-pill">Mes plan {summary.data?.plan_month?.slice(0, 7) ?? "-"}</span>
            <span className="context-pill">Escenario {scenario}</span>
            <span className="context-pill">Fecha corte {status.data?.cut_date ?? "-"}</span>
          </div>
        </div>

        {/* Escenarios tabs */}
        <div className="segmented">
          {scenarios.map((item) => (
            <button className={`segment ${scenario === item ? "active" : ""}`} key={item} onClick={() => setScenario(item)}>
              {item === "CURRENT" ? "Actual" : item === "REALISTIC" ? "Realista" : "Agresivo"}
            </button>
          ))}
        </div>

        {summary.data ? (
          <div className="planner-kpis">
            <Kpi label="Presupuesto actual" value={money(summary.data.current_budget)} />
            <Kpi label="Forecast" value={money(summary.data.forecast)} accent="cyan" />
            <Kpi label="Sugerido" value={money(summary.data.suggested)} accent="violet" />
            <Kpi label="Final" value={money(summary.data.final)} />
            <Kpi label="Ahorro esperado" value={money(summary.data.expected_saving)} accent="green" note={pct(summary.data.expected_saving_pct)} />
          </div>
        ) : (
          <div className="skeleton" />
        )}

        {summary.data ? (
          <div className="surface-lite model-strip" style={{ borderRadius: 14 }}>
            <strong>Para {planMonthName} el modelo recomienda {money(summary.data.final)}.</strong>
            <span className="subtle">
              Son {money(Math.abs(summary.data.forecast - summary.data.final))} {summary.data.final <= summary.data.forecast ? "menos" : "más"} que tu comportamiento proyectado.
            </span>
            <strong className="green">Ahorro: {money(summary.data.expected_saving)} ({pct(summary.data.expected_saving_pct)})</strong>
          </div>
        ) : null}
      </div>

      {/* ========================================================
          1. MOBILE CARDS VIEW (For phones: touch cards)
         ======================================================== */}
      <div className="mobile-only" style={{ display: "grid", gap: 10 }}>
        {(rows.data ?? []).map((row) => (
          <div
            className="surface-lite"
            key={`mobile-${row.id_category}`}
            style={{
              padding: "14px 16px",
              borderRadius: 16,
              border: selected === row.id_category ? "1px solid var(--cyan)" : "1px solid rgba(39, 68, 108, 0.4)",
              cursor: "pointer",
            }}
            onClick={() => handleSelectMobile(row.id_category)}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
              <div>
                <strong style={{ fontSize: 15, display: "block" }}>{row.category}</strong>
                <span className="subtle" style={{ fontSize: 12 }}>{row.subcategory}</span>
              </div>
              <Confidence value={row.confidence} />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, background: "rgba(8, 21, 46, 0.5)", borderRadius: 12, padding: "8px 10px", margin: "8px 0" }}>
              <div>
                <span className="subtle" style={{ fontSize: 10.5, display: "block" }}>Actual</span>
                <strong style={{ fontSize: 13 }}>{money(row.current_budget)}</strong>
              </div>
              <div>
                <span className="subtle" style={{ fontSize: 10.5, display: "block" }}>Forecast</span>
                <strong style={{ fontSize: 13, color: "var(--cyan)" }}>{money(row.forecast_next_month)}</strong>
              </div>
              <div>
                <span className="subtle" style={{ fontSize: 10.5, display: "block" }}>Final</span>
                <strong style={{ fontSize: 13, color: "var(--green)" }}>{money(row.final_budget)}</strong>
              </div>
            </div>

            <button
              className="secondary-button"
              style={{ width: "100%", height: 32, fontSize: 12, gap: 6, marginTop: 4 }}
              onClick={(e) => {
                e.stopPropagation();
                handleSelectMobile(row.id_category);
              }}
            >
              <SlidersHorizontal size={13} />
              <span>Ajustar presupuesto</span>
            </button>
          </div>
        ))}
      </div>

      {/* ========================================================
          2. DESKTOP WORKSPACE (Table + Sticky Inspector)
         ======================================================== */}
      <div className="planner-workspace desktop-only">
        <div className="surface panel-pad">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Categoría</th>
                  <th className="right">Actual</th>
                  <th className="right">MTD</th>
                  <th className="right">Proy. cierre</th>
                  <th className="right">Forecast</th>
                  <th className="right">Sugerido</th>
                  <th className="right">Manual</th>
                  <th className="right">Final</th>
                  <th>Confianza</th>
                </tr>
              </thead>
              <tbody>
                {(rows.data ?? []).map((row) => (
                  <tr
                    className={selected === row.id_category ? "selected" : ""}
                    key={row.id_category}
                    onClick={() => setSelected(row.id_category)}
                  >
                    <td>
                      <strong>{row.category}</strong>
                      <div className="subtle">{row.subcategory}</div>
                    </td>
                    <td className="right">{money(row.current_budget)}</td>
                    <td className="right">{money(row.current_mtd)}</td>
                    <td className="right">{money(row.projected_close)}</td>
                    <td className="right cyan">{money(row.forecast_next_month)}</td>
                    <td className="right violet">{money(row.suggested_budget)}</td>
                    <td className="right">{row.manual_budget == null ? "-" : money(row.manual_budget)}</td>
                    <td className="right">
                      <strong>{money(row.final_budget)}</strong>
                    </td>
                    <td>
                      <Confidence value={row.confidence} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <Inspector
          detail={detail.data}
          selectedRow={selectedRow}
          summary={summary.data}
          scenario={scenario}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ["planner-summary"] });
            queryClient.invalidateQueries({ queryKey: ["planner-categories"] });
            queryClient.invalidateQueries({ queryKey: ["planner-detail"] });
          }}
        />
      </div>

      {/* Mobile Drawer/Modal for Inspector */}
      {mobileModalOpen && selectedRow && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={() => setMobileModalOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="sheet-handle" />
            <div className="modal-header">
              <div>
                <p className="eyebrow">Ajuste de Presupuesto</p>
                <h1>{selectedRow.category}</h1>
                <p className="subtle">{selectedRow.subcategory}</p>
              </div>
              <button className="ghost-button" aria-label="Cerrar" onClick={() => setMobileModalOpen(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="panel-pad">
              <Inspector
                detail={detail.data}
                selectedRow={selectedRow}
                summary={summary.data}
                scenario={scenario}
                onSaved={() => {
                  queryClient.invalidateQueries({ queryKey: ["planner-summary"] });
                  queryClient.invalidateQueries({ queryKey: ["planner-categories"] });
                  queryClient.invalidateQueries({ queryKey: ["planner-detail"] });
                  setMobileModalOpen(false);
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Gráficos de cambio y confianza */}
      <div className="content-grid">
        <div className="surface panel-pad">
          <h2>Dónde cambia tu presupuesto</h2>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={chartData} layout="vertical" margin={{ left: 30, right: 20 }}>
                <XAxis type="number" stroke="#aeb9d0" />
                <YAxis dataKey="name" type="category" stroke="#aeb9d0" width={110} tick={{ fontSize: 11 }} />
                <Bar dataKey="delta" radius={[6, 6, 6, 6]}>
                  {chartData.map((entry) => (
                    <Cell key={entry.name} fill={entry.delta <= 0 ? "#33E6A4" : "#FF5E67"} />
                  ))}
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

function Inspector({
  detail,
  selectedRow,
  summary,
  scenario,
  onSaved,
}: {
  detail?: PlannerDetail;
  selectedRow?: PlannerCategory;
  summary?: PlannerSummary;
  scenario: string;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<string>("");
  const [dirty, setDirty] = useState(false);
  const mutation = useMutation({
    mutationFn: async () => {
      if (!detail || !summary) return null;
      const res = await fetch(`${API_BASE}/planner/overrides/${detail.id_category}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_month: summary.plan_month, scenario, manual_budget_usd: Number(draft) }),
      });
      if (!res.ok) throw new Error("OVERRIDE_FAILED");
      return res.json();
    },
    onSuccess: () => {
      setDirty(false);
      onSaved();
    },
  });

  if (!selectedRow) {
    return (
      <aside className="surface panel-pad inspector empty-state">
        <div>
          <h2>Selecciona una categoría</h2>
          <p>Para ver la recomendación y ajustar tu presupuesto.</p>
        </div>
      </aside>
    );
  }

  const data = detail ?? selectedRow;
  const finalBudgetVal = Number(data.final_budget ?? (data as any).final ?? data.suggested_budget ?? (data as any).suggested ?? 0);
  const manualBudgetVal = data.manual_budget ?? (data as any).manual;
  const draftValue = dirty ? Number(draft || 0) : Number(manualBudgetVal ?? finalBudgetVal);
  const simulatedFinal = summary ? summary.final - finalBudgetVal + draftValue : 0;
  const simulatedSaving = summary ? summary.expected_saving + finalBudgetVal - draftValue : 0;
  const savingPct =
    summary?.expected_saving && summary.expected_saving_pct
      ? simulatedSaving / (summary.expected_saving / summary.expected_saving_pct)
      : 0;

  return (
    <aside className="surface panel-pad inspector">
      <div>
        <h2>{data.category}</h2>
        <p className="subtle">{data.subcategory}</p>
      </div>
      <div className="button-row" style={{ flexWrap: "wrap" }}>
        <span className="status-chip status-muted">{data.forecast_type}</span>
        <Confidence value={data.confidence} />
        <span className="status-chip status-muted">{data.flexibility}</span>
        <span className="status-chip status-muted">{data.is_essential ? "Esencial" : "Flexible"}</span>
      </div>
      <div className="detail-grid">
        <Small label="Actual" value={money(data.current_budget)} />
        <Small label="MTD" value={money(data.current_mtd)} />
        <Small label="Forecast" value={money(data.forecast_next_month)} />
        <Small label="Sugerido" value={money(data.suggested_budget ?? (data as any).suggested)} />
        <Small label="Manual" value={manualBudgetVal == null ? "-" : money(manualBudgetVal)} />
        <Small label="Final" value={money(finalBudgetVal)} />
      </div>
      <div className="surface-lite panel-pad">
        <h2 style={{ fontSize: 14 }}>¿Por qué este monto?</h2>
        <p className="subtle" style={{ fontSize: 12, margin: 0 }}>
          {detail?.confidence_reason ||
            `El predictor usa el comportamiento reciente y clasifica esta categoría como ${data.forecast_type.toLowerCase()} con confianza ${data.confidence.toLowerCase()}.`}
        </p>
      </div>
      <div>
        <label className="metric-label">Presupuesto manual ($ USD)</label>
        <input
          className="number-input"
          type="number"
          min="0"
          value={dirty ? draft : manualBudgetVal ?? finalBudgetVal}
          onChange={(event) => {
            setDraft(event.target.value);
            setDirty(true);
          }}
        />
      </div>
      {dirty ? (
        <div className="surface-lite panel-pad">
          <strong className="yellow">Cambios sin guardar</strong>
          <p className="subtle" style={{ margin: "4px 0 0" }}>
            Nuevo presupuesto mensual: {money(simulatedFinal)}. Ahorro esperado: {money(simulatedSaving)} ({pct(savingPct)})
          </p>
        </div>
      ) : null}
      {mutation.isSuccess && !dirty ? <strong className="green">Ajuste guardado exitosamente</strong> : null}
      <div className="button-row">
        <button
          className="secondary-button"
          disabled={!dirty}
          onClick={() => {
            setDirty(false);
            setDraft("");
          }}
        >
          Cancelar
        </button>
        <button className="primary-button" disabled={!dirty || mutation.isPending} onClick={() => mutation.mutate()}>
          {mutation.isPending ? "Guardando..." : "Guardar ajuste"}
        </button>
      </div>
    </aside>
  );
}

function Kpi({ label, value, accent, note }: { label: string; value: string; accent?: string; note?: string }) {
  return (
    <div className="metric-tile">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${accent ?? ""}`}>{value}</div>
      {note ? <div className="metric-note">{note}</div> : null}
    </div>
  );
}

function Small({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-cell">
      <div className="metric-label">{label}</div>
      <strong>{value}</strong>
    </div>
  );
}

function Confidence({ value }: { value: string }) {
  const cls = value === "HIGH" ? "conf-high" : value === "MEDIUM" ? "conf-medium" : "conf-low";
  return <span className={`confidence-chip ${cls}`}>{value}</span>;
}
