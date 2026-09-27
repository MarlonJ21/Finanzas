"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, money, type MovementResponse } from "../../lib/api";

const pageSize = 50;

export default function MovementsPage() {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [filters, setFilters] = useState({ date_from: "", date_to: "", domain: "", category: "", subcategory: "", account: "" });

  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(search), 350);
    return () => window.clearTimeout(id);
  }, [search]);

  useEffect(() => setOffset(0), [debounced, filters]);

  const query = useMemo(() => {
    const params = new URLSearchParams({ limit: String(pageSize), offset: String(offset) });
    Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
    if (debounced) params.set("search", debounced);
    return params.toString();
  }, [offset, filters, debounced]);

  const data = useQuery({ queryKey: ["movements", query], queryFn: () => api<MovementResponse>(`/movements?${query}`) });
  const items = data.data?.items ?? [];
  const total = data.data?.total ?? 0;

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Explorador financiero</p>
          <h1>Movimientos</h1>
          <p className="subtle">Busca, filtra y revisa el detalle sin cargar todo el historial al cliente.</p>
        </div>
      </div>
      <div className="surface panel-pad page">
        <div className="filters">
          <Field label="Desde"><input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} /></Field>
          <Field label="Hasta"><input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} /></Field>
          <Field label="Dominio"><select value={filters.domain} onChange={(e) => setFilters({ ...filters, domain: e.target.value })}><option value="">Todos</option><option>PERSONAL</option><option>NEGOCIO</option><option>PATRIMONIAL</option></select></Field>
          <Field label="Categoria"><input value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })} placeholder="Alimentacion" /></Field>
          <Field label="Subcategoria"><input value={filters.subcategory} onChange={(e) => setFilters({ ...filters, subcategory: e.target.value })} placeholder="Mercado" /></Field>
          <Field label="Cuenta"><input value={filters.account} onChange={(e) => setFilters({ ...filters, account: e.target.value })} placeholder="Cuenta" /></Field>
        </div>
        <div className="field">
          <label><Search size={14} /> Buscar descripcion</label>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Yummy, farmacia, transferencia..." />
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Fecha</th><th>Descripcion</th><th>Categoria</th><th>Subcategoria</th><th>Cuenta</th><th className="right">Monto</th></tr></thead>
            <tbody>
              {items.map((row, index) => {
                const typeLower = (row.type ?? "").toLowerCase();
                const isIngreso = typeLower.includes("ingreso");
                const isEgreso = typeLower.includes("egreso");
                const colorClass = isIngreso ? "green" : isEgreso ? "red" : "";
                return (
                  <tr key={`${row.date}-${row.description}-${index}`}>
                    <td>{row.date}</td>
                    <td><strong>{row.description}</strong><div className="subtle">{row.domain}</div></td>
                    <td>{row.category}</td>
                    <td>{row.subcategory}</td>
                    <td>{row.account}</td>
                    <td className={`right ${colorClass}`}><strong>{money(row.amount_usd)}</strong></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!data.isLoading && !items.length ? <div className="empty-state"><div><h2>Sin resultados</h2><p>Ajusta los filtros o limpia la busqueda.</p></div></div> : null}
        </div>
        <div className="pagination">
          <span className="subtle">{total ? `${offset + 1}-${Math.min(offset + pageSize, total)} de ${total}` : "0 movimientos"}</span>
          <div className="button-row">
            <button className="secondary-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Anterior</button>
            <button className="secondary-button" disabled={offset + pageSize >= total} onClick={() => setOffset(offset + pageSize)}>Siguiente</button>
          </div>
        </div>
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="field"><label>{label}</label>{children}</div>;
}
