import { api, money, pct } from "../../lib/api";

type PlannerSummary = {
  current_budget: number;
  forecast: number;
  suggested: number;
  final: number;
  expected_saving: number;
  expected_saving_pct: number;
  confidence_high: number;
  confidence_medium: number;
  confidence_low: number;
  plan_month: string;
  state: string;
};

type PlannerCategory = {
  id_category: string;
  category: string;
  subcategory: string;
  current_budget: number;
  current_mtd: number;
  projected_close: number;
  forecast_next_month: number;
  suggested_budget: number;
  manual_budget: number | null;
  final_budget: number;
  confidence: string;
};

export default async function PlannerPage() {
  const [summary, rows] = await Promise.all([
    api<PlannerSummary>("/planner/summary?scenario=REALISTIC"),
    api<PlannerCategory[]>("/planner/categories?scenario=REALISTIC")
  ]);

  return (
    <section className="page grid">
      <div className="grid kpis">
        <div className="card"><div className="label">Presupuesto actual</div><div className="value">{money(summary.current_budget)}</div></div>
        <div className="card"><div className="label">Forecast proximo mes</div><div className="value cyan">{money(summary.forecast)}</div></div>
        <div className="card"><div className="label">Presupuesto sugerido</div><div className="value violet">{money(summary.suggested)}</div></div>
        <div className="card"><div className="label">Ahorro esperado</div><div className="value green">{money(summary.expected_saving)}</div><div className="label">{pct(summary.expected_saving_pct)}</div></div>
      </div>
      <div className="panel">
        <h1 className="section-title">Planificador proximo mes</h1>
        <table>
          <thead><tr><th>Categoria</th><th>Subcategoria</th><th className="right">Actual</th><th className="right">MTD</th><th className="right">Proy. cierre</th><th className="right">Forecast</th><th className="right">Sugerido</th><th className="right">Final</th><th>Confianza</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id_category}>
                <td>{row.category}</td><td>{row.subcategory}</td><td className="right">{money(row.current_budget)}</td><td className="right">{money(row.current_mtd)}</td><td className="right">{money(row.projected_close)}</td><td className="right">{money(row.forecast_next_month)}</td><td className="right">{money(row.suggested_budget)}</td><td className="right">{money(row.final_budget)}</td><td>{row.confidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
