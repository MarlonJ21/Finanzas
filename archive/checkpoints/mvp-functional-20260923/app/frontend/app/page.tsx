import { Activity, PiggyBank, WalletCards, AlertTriangle } from "lucide-react";
import { api, money, pct } from "../lib/api";

type Summary = {
  income_sustainable: number;
  personal_spend: number;
  monthly_budget: number;
  monthly_available: number;
  biweekly_spend: number;
  biweekly_budget: number;
  safe_to_spend: number;
  saving_target: number;
  saving_rate: number;
};

type Status = {
  last_update: string | null;
  cut_date: string | null;
  movement_count: number;
  exact_duplicates: number;
  possible_duplicates: number;
  missing_fx: number;
  pending_classification: number;
};

type Category = {
  category: string;
  subcategory: string;
  spent: number;
  budget: number;
  available: number;
  status: string;
};

export default async function HomePage() {
  const [summary, status, categories] = await Promise.all([
    api<Summary>("/dashboard/summary?month=2026-09&scenario=REALISTIC&biweekly_period=1"),
    api<Status>("/data/status"),
    api<Category[]>("/dashboard/categories?month=2026-09&scenario=REALISTIC")
  ]);

  return (
    <section className="page grid">
      <div className="grid kpis">
        <div className="card"><div className="label"><WalletCards size={16} /> Presupuesto mensual</div><div className="value">{money(summary.monthly_budget)}</div></div>
        <div className="card"><div className="label"><Activity size={16} /> Gasto personal</div><div className="value cyan">{money(summary.personal_spend)}</div></div>
        <div className="card"><div className="label"><PiggyBank size={16} /> Ahorro esperado</div><div className="value green">{money(summary.saving_target)}</div><div className="label">{pct(summary.saving_rate)}</div></div>
        <div className="card"><div className="label"><AlertTriangle size={16} /> Alertas calidad</div><div className="value violet">{status.possible_duplicates}</div><div className="label">duplicados posibles</div></div>
      </div>
      <div className="grid two">
        <div className="panel">
          <h1 className="section-title">Presupuesto por categoria</h1>
          <table>
            <thead><tr><th>Categoria</th><th>Subcategoria</th><th className="right">Gasto</th><th className="right">Presupuesto</th><th className="right">Disponible</th></tr></thead>
            <tbody>
              {categories.slice(0, 16).map((row) => (
                <tr key={`${row.category}-${row.subcategory}`}>
                  <td>{row.category}</td><td>{row.subcategory}</td><td className="right">{money(row.spent)}</td><td className="right">{money(row.budget)}</td><td className="right">{money(row.available)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h2 className="section-title">Estado de datos</h2>
          <p className="label">Corte: {status.cut_date}</p>
          <p className="label">Movimientos: {status.movement_count}</p>
          <p className="label">Duplicados exactos: {status.exact_duplicates}</p>
          <p className="label">FX faltante: {status.missing_fx}</p>
          <p className="label">Pendientes clasificacion: {status.pending_classification}</p>
        </div>
      </div>
    </section>
  );
}
