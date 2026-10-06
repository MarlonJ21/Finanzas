"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Car,
  CreditCard,
  DollarSign,
  Filter,
  HeartPulse,
  Home,
  Laptop,
  Search,
  ShoppingBag,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState, Suspense } from "react";
import { api, money, type MovementResponse } from "../../lib/api";

const pageSize = 50;

export default function MovementsPage() {
  return (
    <Suspense fallback={<div className="page"><div className="skeleton" /><div className="skeleton" /></div>}>
      <MovementsContent />
    </Suspense>
  );
}

function MovementsContent() {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [quickFilter, setQuickFilter] = useState<"ALL" | "PERSONAL" | "NEGOCIO" | "INGRESO" | "EGRESO">("ALL");

  const [filters, setFilters] = useState({
    date_from: "",
    date_to: "",
    domain: "",
    category: "",
    subcategory: "",
    account: "",
  });

  // Check URL parameters for category filtering (e.g. from alerts or category click)
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const catParam = params.get("category");
      if (catParam) {
        setFilters((prev) => ({ ...prev, category: catParam }));
      }
      const accParam = params.get("account");
      if (accParam) {
        setFilters((prev) => ({ ...prev, account: accParam }));
      }
    }
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(search), 300);
    return () => window.clearTimeout(id);
  }, [search]);

  useEffect(() => setOffset(0), [debounced, filters, quickFilter]);

  const query = useMemo(() => {
    const params = new URLSearchParams({ limit: String(pageSize), offset: String(offset) });
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });

    if (quickFilter === "PERSONAL") params.set("domain", "PERSONAL");
    else if (quickFilter === "NEGOCIO") params.set("domain", "NEGOCIO");
    else if (quickFilter === "INGRESO") params.set("type", "Ingreso");
    else if (quickFilter === "EGRESO") params.set("type", "Egreso");

    if (debounced) params.set("search", debounced);
    return params.toString();
  }, [offset, filters, debounced, quickFilter]);

  const data = useQuery({
    queryKey: ["movements", query],
    queryFn: () => api<MovementResponse>(`/movements?${query}`),
  });

  const items = data.data?.items ?? [];
  const total = data.data?.total ?? 0;

  const hasActiveCategoryFilter = Boolean(filters.category);

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Explorador financiero</p>
          <h1>Movimientos</h1>
          <p className="subtle">Historial detallado de todas tus transacciones bancarias y de billeteras.</p>
        </div>
      </div>

      <div className="surface panel-pad page">
        {/* Search bar + Filter toggle */}
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div className="field" style={{ flex: 1, margin: 0 }}>
            <div style={{ position: "relative" }}>
              <Search size={16} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
              <input
                style={{ paddingLeft: 38 }}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar por descripción (Yummy, Farmacia, Cashea...)"
              />
              {search && (
                <button
                  className="ghost-button"
                  style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", padding: 4 }}
                  onClick={() => setSearch("")}
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>
          <button
            className={`secondary-button ${showAdvancedFilters ? "active" : ""}`}
            style={{ padding: "0 12px", minHeight: 38 }}
            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            title="Filtros avanzados"
          >
            <SlidersHorizontal size={16} />
            <span className="desktop-only">Filtros</span>
          </button>
        </div>

        {/* Quick filter chips */}
        <div className="filter-chips-row">
          <button
            className={`filter-chip ${quickFilter === "ALL" && !hasActiveCategoryFilter ? "active" : ""}`}
            onClick={() => { setQuickFilter("ALL"); setFilters((f) => ({ ...f, category: "" })); }}
          >
            Todos
          </button>
          <button
            className={`filter-chip ${quickFilter === "PERSONAL" ? "active" : ""}`}
            onClick={() => setQuickFilter((prev) => (prev === "PERSONAL" ? "ALL" : "PERSONAL"))}
          >
            Personal
          </button>
          <button
            className={`filter-chip ${quickFilter === "NEGOCIO" ? "active" : ""}`}
            onClick={() => setQuickFilter((prev) => (prev === "NEGOCIO" ? "ALL" : "NEGOCIO"))}
          >
            Negocio
          </button>
          <button
            className={`filter-chip ${quickFilter === "EGRESO" ? "active" : ""}`}
            onClick={() => setQuickFilter((prev) => (prev === "EGRESO" ? "ALL" : "EGRESO"))}
          >
            Solo Egresos
          </button>
          <button
            className={`filter-chip ${quickFilter === "INGRESO" ? "active" : ""}`}
            onClick={() => setQuickFilter((prev) => (prev === "INGRESO" ? "ALL" : "INGRESO"))}
          >
            Solo Ingresos
          </button>
        </div>

        {quickFilter === "NEGOCIO" && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, background: "rgba(51, 230, 164, 0.1)", border: "1px solid rgba(51, 230, 164, 0.3)", borderRadius: 12, padding: "10px 14px", flexWrap: "wrap" }}>
            <span style={{ fontSize: 13, color: "var(--green)", fontWeight: 650 }}>
              🛍️ Mostrando movimientos comerciales de <strong>PremiadosVE</strong> (100% aislados de tus finanzas personales).
            </span>
            <Link
              href="/premiados"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 12px",
                borderRadius: 8,
                background: "rgba(51, 230, 164, 0.2)",
                color: "var(--green)",
                fontSize: "0.8rem",
                fontWeight: 700,
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              Ver Panel PremiadosVE →
            </Link>
          </div>
        )}

        {/* Tag when arriving from an alert */}
        {hasActiveCategoryFilter && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, background: "rgba(32, 215, 232, 0.12)", border: "1px solid rgba(32, 215, 232, 0.35)", borderRadius: 12, padding: "8px 12px" }}>
            <span style={{ fontSize: 13, color: "var(--cyan)", fontWeight: 700 }}>
              Filtrado por categoría: <strong>{filters.category}</strong>
            </span>
            <button
              className="ghost-button"
              style={{ marginLeft: "auto", padding: "2px 8px", fontSize: 12, color: "var(--cyan)" }}
              onClick={() => setFilters((f) => ({ ...f, category: "" }))}
            >
              ✕ Quitar filtro
            </button>
          </div>
        )}

        {/* Collapsible advanced filters */}
        {showAdvancedFilters && (
          <div className="surface-lite panel-pad" style={{ display: "grid", gap: 12 }}>
            <div className="filters">
              <Field label="Desde">
                <input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} />
              </Field>
              <Field label="Hasta">
                <input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} />
              </Field>
              <Field label="Categoría">
                <input value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })} placeholder="Alimentación" />
              </Field>
              <Field label="Subcategoría">
                <input value={filters.subcategory} onChange={(e) => setFilters({ ...filters, subcategory: e.target.value })} placeholder="Mercado" />
              </Field>
              <Field label="Cuenta">
                <input value={filters.account} onChange={(e) => setFilters({ ...filters, account: e.target.value })} placeholder="BNC, Binance..." />
              </Field>
              <div style={{ display: "flex", alignItems: "flex-end" }}>
                <button
                  className="secondary-button"
                  style={{ width: "100%", height: 38 }}
                  onClick={() => setFilters({ date_from: "", date_to: "", domain: "", category: "", subcategory: "", account: "" })}
                >
                  Limpiar filtros
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================
            1. MOBILE FEED VIEW (For Phones: sleek card layout)
           ======================================================== */}
        <div className="tx-feed mobile-only">
          {items.map((row, index) => {
            const typeLower = (row.type ?? "").toLowerCase();
            const isIngreso = typeLower.includes("ingreso");
            const isEgreso = typeLower.includes("egreso");
            const Icon = getTxIcon(row.category, row.subcategory, isIngreso);
            const iconClass = isIngreso ? "ingreso" : isEgreso ? "egreso" : "transf";
            const amountColor = isIngreso ? "var(--green)" : "#ffffff";

            return (
              <div className="tx-card" key={`mobile-${row.date}-${row.description}-${index}`}>
                <div className={`tx-icon ${iconClass}`}>
                  <Icon size={20} />
                </div>
                <div className="tx-details">
                  <div className="tx-desc">{row.description}</div>
                  <div className="tx-meta">
                    <span className="tx-account-pill">{row.account || "Cuenta"}</span>
                    <span>{row.category}</span>
                    {row.subcategory ? <span>• {row.subcategory}</span> : null}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="tx-amount" style={{ color: amountColor }}>
                    {isIngreso ? "+" : "-"}{money(row.amount_usd)}
                  </div>
                  <div className="subtle" style={{ fontSize: 11, marginTop: 2 }}>{row.date}</div>
                </div>
              </div>
            );
          })}
          {!data.isLoading && !items.length && (
            <div className="empty-state">
              <div>
                <h2>Sin resultados</h2>
                <p>No se encontraron movimientos con los filtros actuales.</p>
              </div>
            </div>
          )}
        </div>

        {/* ========================================================
            2. DESKTOP TABLE VIEW (For wide monitors)
           ======================================================== */}
        <div className="table-wrap desktop-only">
          <table className="data-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Descripción</th>
                <th>Categoría</th>
                <th>Subcategoría</th>
                <th>Cuenta</th>
                <th className="right">Monto</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row, index) => {
                const typeLower = (row.type ?? "").toLowerCase();
                const isIngreso = typeLower.includes("ingreso");
                const isEgreso = typeLower.includes("egreso");
                const colorClass = isIngreso ? "green" : isEgreso ? "red" : "";
                return (
                  <tr key={`desktop-${row.date}-${row.description}-${index}`}>
                    <td>{row.date}</td>
                    <td>
                      <strong>{row.description}</strong>
                      <div className="subtle">{row.domain}</div>
                    </td>
                    <td>{row.category}</td>
                    <td>{row.subcategory}</td>
                    <td>{row.account}</td>
                    <td className={`right ${colorClass}`}>
                      <strong>{isIngreso ? "+" : "-"}{money(row.amount_usd)}</strong>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!data.isLoading && !items.length && (
            <div className="empty-state">
              <div>
                <h2>Sin resultados</h2>
                <p>Ajusta los filtros o limpia la búsqueda.</p>
              </div>
            </div>
          )}
        </div>

        {/* Pagination */}
        <div className="pagination">
          <span className="subtle">
            {total ? `${offset + 1}-${Math.min(offset + pageSize, total)} de ${total}` : "0 movimientos"}
          </span>
          <div className="button-row">
            <button
              className="secondary-button"
              disabled={offset === 0}
              onClick={() => {
                setOffset(Math.max(0, offset - pageSize));
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            >
              Anterior
            </button>
            <button
              className="secondary-button"
              disabled={offset + pageSize >= total}
              onClick={() => {
                setOffset(offset + pageSize);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            >
              Siguiente
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
    </div>
  );
}

function getTxIcon(category: string, subcategory: string, isIngreso: boolean) {
  if (isIngreso) return ArrowDownLeft;
  const c = `${category} ${subcategory}`.toLowerCase();
  if (c.includes("aliment") || c.includes("comida") || c.includes("super") || c.includes("snack") || c.includes("cena")) return ShoppingBag;
  if (c.includes("movilidad") || c.includes("transporte") || c.includes("uber") || c.includes("gasolina") || c.includes("taxi") || c.includes("traslado")) return Car;
  if (c.includes("suscrip") || c.includes("herramienta") || c.includes("software") || c.includes("internet") || c.includes("streaming")) return Laptop;
  if (c.includes("salud") || c.includes("farmacia") || c.includes("medico") || c.includes("clinica")) return HeartPulse;
  if (c.includes("casa") || c.includes("hogar") || c.includes("alquiler") || c.includes("servicios")) return Home;
  if (c.includes("deuda") || c.includes("cashea") || c.includes("prestamo") || c.includes("tarjeta")) return CreditCard;
  return ArrowUpRight;
}
