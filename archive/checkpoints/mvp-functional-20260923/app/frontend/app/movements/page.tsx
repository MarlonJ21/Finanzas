import { api, money } from "../../lib/api";

type Movement = {
  date: string;
  description: string;
  domain: string;
  category: string;
  subcategory: string;
  account: string;
  amount_usd: number;
  type: string;
};

type MovementResponse = {
  total: number;
  items: Movement[];
};

export default async function MovementsPage() {
  const data = await api<MovementResponse>("/movements?limit=100");

  return (
    <section className="page panel">
      <h1 className="section-title">Movimientos</h1>
      <table>
        <thead><tr><th>Fecha</th><th>Descripcion</th><th>Dominio</th><th>Categoria</th><th>Cuenta</th><th className="right">USD</th></tr></thead>
        <tbody>
          {data.items.map((row, index) => (
            <tr key={`${row.date}-${row.description}-${index}`}>
              <td>{row.date}</td><td>{row.description}</td><td>{row.domain}</td><td>{row.category} / {row.subcategory}</td><td>{row.account}</td><td className="right">{money(row.amount_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
