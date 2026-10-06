"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Briefcase,
  Calendar,
  CheckCircle2,
  ChevronRight,
  CreditCard,
  DollarSign,
  Filter,
  Package,
  Search,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Truck,
  Wallet,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  api,
  money,
  pct,
  type BusinessMovementsResponse,
  type BusinessSummary,
} from "../../lib/api";

export default function PremiadosPage() {
  const [selectedMonth, setSelectedMonth] = useState<string>("2026-10");
  const [selectedType, setSelectedType] = useState<"all" | "Ingreso" | "Egreso">("all");
  const [search, setSearch] = useState("");

  const summaryQuery = useQuery({
    queryKey: ["business-summary", selectedMonth],
    queryFn: () =>
      api<BusinessSummary>(
        `/business/summary?month=${encodeURIComponent(selectedMonth)}`
      ),
  });

  const movementsQuery = useQuery({
    queryKey: ["business-movements", selectedMonth, selectedType, search],
    queryFn: () => {
      const params = new URLSearchParams({
        month: selectedMonth,
        type: selectedType,
        limit: "100",
      });
      if (search.trim()) params.set("search", search.trim());
      return api<BusinessMovementsResponse>(`/business/movements?${params.toString()}`);
    },
  });

  const summary = summaryQuery.data;
  const movements = movementsQuery.data?.items ?? [];

  const availableMonths = summary?.available_months ?? ["2026-10", "2026-09", "2026-08"];

  const formatMonthLabel = (m: string) => {
    if (m === "all") return "Histórico Total";
    const [year, monthNum] = m.split("-");
    const d = new Date(parseInt(year, 10), parseInt(monthNum, 10) - 1, 1);
    const name = d.toLocaleDateString("es-VE", { month: "long" });
    return `${name.charAt(0).toUpperCase() + name.slice(1)} ${year}`;
  };

  return (
    <section className="page">
      {/* Header */}
      <div className="page-header" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <p className="eyebrow" style={{ margin: 0 }}>Unidad de Negocio</p>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                background: "rgba(51, 230, 164, 0.12)",
                color: "var(--green)",
                border: "1px solid rgba(51, 230, 164, 0.3)",
                borderRadius: 9999,
                padding: "2px 10px",
                fontSize: "0.75rem",
                fontWeight: 700,
              }}
            >
              <ShieldCheck size={14} /> 100% Desacoplado de finanzas personales
            </span>
          </div>
          <h1 style={{ display: "flex", alignItems: "center", gap: 12, margin: 0 }}>
            <span
              style={{
                display: "grid",
                width: 38,
                height: 38,
                placeItems: "center",
                background: "rgba(32, 215, 232, 0.15)",
                border: "1px solid rgba(32, 215, 232, 0.4)",
                borderRadius: 12,
                color: "var(--cyan)",
              }}
            >
              <ShoppingBag size={22} />
            </span>
            PremiadosVE
          </h1>
          <p className="subtle" style={{ margin: 0, maxWidth: 760 }}>
            Centro de control operativo: ventas, costos por publicidad/delivery y rentabilidad neta.
            Tus ingresos por ventas no afectan tu cálculo salarial ni distorsionan tu presupuesto personal.
          </p>
        </div>
      </div>

      {/* Period Selector Tabs */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
          padding: "10px 14px",
          background: "rgba(17, 36, 69, 0.6)",
          border: "1px solid var(--border)",
          borderRadius: 14,
        }}
      >
        <span style={{ fontSize: "0.82rem", color: "var(--muted)", fontWeight: 700, display: "flex", alignItems: "center", gap: 6, marginRight: 4 }}>
          <Calendar size={15} /> Período:
        </span>
        {availableMonths.map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setSelectedMonth(m)}
            style={{
              padding: "6px 14px",
              borderRadius: 10,
              border: selectedMonth === m ? "1px solid var(--cyan)" : "1px solid rgba(39, 68, 108, 0.5)",
              background: selectedMonth === m ? "rgba(32, 215, 232, 0.16)" : "transparent",
              color: selectedMonth === m ? "#ffffff" : "var(--muted)",
              fontWeight: selectedMonth === m ? 750 : 500,
              fontSize: "0.85rem",
              transition: "all 120ms ease",
            }}
          >
            {formatMonthLabel(m)}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setSelectedMonth("all")}
          style={{
            padding: "6px 14px",
            borderRadius: 10,
            border: selectedMonth === "all" ? "1px solid var(--cyan)" : "1px solid rgba(39, 68, 108, 0.5)",
            background: selectedMonth === "all" ? "rgba(32, 215, 232, 0.16)" : "transparent",
            color: selectedMonth === "all" ? "#ffffff" : "var(--muted)",
            fontWeight: selectedMonth === "all" ? 750 : 500,
            fontSize: "0.85rem",
            transition: "all 120ms ease",
          }}
        >
          Histórico Completo
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid-4" style={{ marginTop: 6 }}>
        {/* Card 1: Ventas */}
        <div className="decision-card">
          <div className="decision-header">
            <div>
              <div className="decision-title">Ventas Totales (Ingresos)</div>
              <div className="decision-val" style={{ color: "var(--green)" }}>
                {summary ? money(summary.total_sales_usd) : "..."}
              </div>
            </div>
            <div className="decision-icon green">
              <TrendingUp size={18} />
            </div>
          </div>
          <div className="decision-desc">
            {summary
              ? `${summary.sales_count} ventas concretadas • Ticket prom: ${money(summary.average_ticket_usd)}`
              : "Cargando ventas..."}
          </div>
        </div>

        {/* Card 2: Costos Operativos */}
        <div className="decision-card">
          <div className="decision-header">
            <div>
              <div className="decision-title">Costos Operativos (Egresos)</div>
              <div className="decision-val" style={{ color: "var(--red)" }}>
                {summary ? money(summary.total_expenses_usd) : "..."}
              </div>
            </div>
            <div className="decision-icon" style={{ background: "rgba(255, 94, 103, 0.12)", color: "var(--red)" }}>
              <TrendingDown size={18} />
            </div>
          </div>
          <div className="decision-desc">
            {summary
              ? `${summary.expenses_count} desembolsos (Meta Ads, envíos, papelería)`
              : "Cargando egresos..."}
          </div>
        </div>

        {/* Card 3: Utilidad Neta */}
        <div className="decision-card" style={{ borderColor: "rgba(51, 230, 164, 0.35)", background: "rgba(13, 35, 58, 0.85)" }}>
          <div className="decision-header">
            <div>
              <div className="decision-title" style={{ color: "var(--green)" }}>Ganancia Neta (Utilidad)</div>
              <div className="decision-val" style={{ color: summary && summary.net_profit_usd >= 0 ? "var(--green)" : "var(--red)" }}>
                {summary ? `${summary.net_profit_usd >= 0 ? "+" : ""}${money(summary.net_profit_usd)}` : "..."}
              </div>
            </div>
            <div className="decision-icon green">
              <Sparkles size={18} />
            </div>
          </div>
          <div className="decision-desc" style={{ color: "#ffffff", fontWeight: 600 }}>
            {summary
              ? `Margen comercial: ${pct(summary.profit_margin_pct)} de ganancia sobre ventas`
              : "Calculando margen..."}
          </div>
        </div>

        {/* Card 4: Histórico Acumulado */}
        <div className="decision-card">
          <div className="decision-header">
            <div>
              <div className="decision-title">Histórico de Negocio</div>
              <div className="decision-val" style={{ color: "var(--cyan)" }}>
                {summary ? money(summary.all_time_sales_usd) : "..."}
              </div>
            </div>
            <div className="decision-icon">
              <Wallet size={18} />
            </div>
          </div>
          <div className="decision-desc">
            {summary
              ? `Utilidad total acumulada: +${money(summary.all_time_net_profit_usd)} en todos los períodos`
              : "Cargando acumulados..."}
          </div>
        </div>
      </div>

      {/* Breakdown Grid: Costos Operativos + Canales de Cobro + Evolución Mensual */}
      <div className="grid-2" style={{ marginTop: 10 }}>
        {/* Costos Operativos */}
        <div className="panel-card" style={{ padding: 20 }}>
          <div className="section-title-wrap" style={{ marginBottom: 14 }}>
            <h3 className="section-title" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "1.05rem" }}>
              <Package size={18} style={{ color: "var(--cyan)" }} /> Desglose de Costos Operativos
            </h3>
            <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
              Total: {summary ? money(summary.total_expenses_usd) : "..."}
            </span>
          </div>

          {summary && summary.expenses_by_subcategory.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {summary.expenses_by_subcategory.map((item) => (
                <div key={item.subcategory} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.86rem" }}>
                    <span style={{ fontWeight: 650, color: "var(--text)" }}>{item.subcategory}</span>
                    <span style={{ fontWeight: 750, color: "#ffffff" }}>
                      {money(item.amount_usd)}{" "}
                      <span style={{ color: "var(--muted)", fontWeight: 500, fontSize: "0.78rem" }}>
                        ({pct(item.pct)})
                      </span>
                    </span>
                  </div>
                  <div style={{ height: 6, background: "rgba(255, 255, 255, 0.08)", borderRadius: 9999, overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(item.pct * 100, 100)}%`,
                        background: item.subcategory.toLowerCase().includes("ads") || item.subcategory.toLowerCase().includes("publicidad")
                          ? "linear-gradient(90deg, #c26cff, #20d7e8)"
                          : "linear-gradient(90deg, #20d7e8, #33e6a4)",
                        borderRadius: 9999,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: "30px 20px", textAlign: "center", color: "var(--muted)", fontSize: "0.88rem" }}>
              Sin egresos operativos registrados para este período.
            </div>
          )}

          {/* Canales de Cobro */}
          <div style={{ marginTop: 22, paddingTop: 16, borderTop: "1px solid rgba(39, 68, 108, 0.45)" }}>
            <h4 style={{ margin: "0 0 10px 0", fontSize: "0.85rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
              Canales de Cobro ({summary?.month === "all" ? "Histórico" : formatMonthLabel(summary?.month ?? "")})
            </h4>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {summary?.sales_by_account.map((acc) => (
                <div
                  key={acc.account}
                  style={{
                    flex: "1 1 calc(33.3% - 10px)",
                    minWidth: 120,
                    padding: "8px 12px",
                    borderRadius: 10,
                    background: "rgba(13, 29, 58, 0.5)",
                    border: "1px solid rgba(39, 68, 108, 0.35)",
                  }}
                >
                  <div style={{ fontSize: "0.76rem", color: "var(--muted)" }}>{acc.account}</div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 750, color: "var(--green)" }}>{money(acc.amount_usd)}</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--muted)" }}>{acc.count} cobros ({pct(acc.pct)})</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Evolución Mes a Mes */}
        <div className="panel-card" style={{ padding: 20 }}>
          <div className="section-title-wrap" style={{ marginBottom: 14 }}>
            <h3 className="section-title" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "1.05rem" }}>
              <TrendingUp size={18} style={{ color: "var(--green)" }} /> Rendimiento Mensual de PremiadosVE
            </h3>
            <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Histórico Comparativo</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {summary?.monthly_trend.map((row) => {
              const isSelected = selectedMonth === row.month;
              return (
                <div
                  key={row.month}
                  onClick={() => setSelectedMonth(row.month)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 14px",
                    borderRadius: 12,
                    background: isSelected ? "rgba(32, 215, 232, 0.12)" : "rgba(13, 29, 58, 0.6)",
                    border: isSelected ? "1px solid var(--cyan)" : "1px solid rgba(39, 68, 108, 0.35)",
                    cursor: "pointer",
                    transition: "all 120ms ease",
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 750, fontSize: "0.92rem", color: isSelected ? "var(--cyan)" : "#ffffff" }}>
                      {formatMonthLabel(row.month)}
                    </div>
                    <div style={{ fontSize: "0.76rem", color: "var(--muted)", marginTop: 2 }}>
                      Ventas: <strong style={{ color: "var(--green)" }}>{money(row.sales_usd)}</strong> ({row.sales_count} vtas) | Costos: <span style={{ color: "var(--red)" }}>{money(row.expenses_usd)}</span>
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontWeight: 800, fontSize: "0.95rem", color: row.net_profit_usd >= 0 ? "var(--green)" : "var(--red)" }}>
                      {row.net_profit_usd >= 0 ? "+" : ""}{money(row.net_profit_usd)}
                    </div>
                    <div style={{ fontSize: "0.74rem", color: "var(--muted)" }}>
                      Margen: {pct(row.margin_pct)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ marginTop: 14, padding: "10px 14px", borderRadius: 10, background: "rgba(51, 230, 164, 0.08)", border: "1px solid rgba(51, 230, 164, 0.25)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--green)" }}>Utilidad Acumulada del Negocio:</span>
            <span style={{ fontSize: "1.05rem", fontWeight: 850, color: "var(--green)" }}>+{money(summary?.all_time_net_profit_usd ?? 0)}</span>
          </div>
        </div>
      </div>

      {/* Transacciones de PremiadosVE */}
      <div className="panel-card" style={{ marginTop: 16, padding: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
          <div>
            <h3 className="section-title" style={{ margin: 0, fontSize: "1.1rem" }}>Libro de Movimientos Comerciales</h3>
            <p className="subtle" style={{ margin: "2px 0 0 0", fontSize: "0.82rem" }}>
              Mostrando {movements.length} transacciones registradas de PremiadosVE
            </p>
          </div>

          {/* Search & Type filter pills */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <div style={{ position: "relative", minWidth: 200 }}>
              <Search size={15} style={{ position: "absolute", left: 10, top: 10, color: "var(--muted)" }} />
              <input
                type="text"
                placeholder="Buscar cliente, kit, detalle..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{
                  width: "100%",
                  padding: "7px 10px 7px 32px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "rgba(8, 21, 46, 0.6)",
                  color: "#ffffff",
                  fontSize: "0.82rem",
                }}
              />
            </div>

            <div style={{ display: "flex", gap: 4, background: "rgba(8, 21, 46, 0.6)", padding: 3, borderRadius: 8, border: "1px solid var(--border)" }}>
              <button
                type="button"
                onClick={() => setSelectedType("all")}
                style={{
                  padding: "5px 10px",
                  borderRadius: 6,
                  border: 0,
                  background: selectedType === "all" ? "rgba(32, 215, 232, 0.2)" : "transparent",
                  color: selectedType === "all" ? "#ffffff" : "var(--muted)",
                  fontSize: "0.78rem",
                  fontWeight: selectedType === "all" ? 700 : 500,
                }}
              >
                Todas
              </button>
              <button
                type="button"
                onClick={() => setSelectedType("Ingreso")}
                style={{
                  padding: "5px 10px",
                  borderRadius: 6,
                  border: 0,
                  background: selectedType === "Ingreso" ? "rgba(51, 230, 164, 0.2)" : "transparent",
                  color: selectedType === "Ingreso" ? "var(--green)" : "var(--muted)",
                  fontSize: "0.78rem",
                  fontWeight: selectedType === "Ingreso" ? 700 : 500,
                }}
              >
                Ventas
              </button>
              <button
                type="button"
                onClick={() => setSelectedType("Egreso")}
                style={{
                  padding: "5px 10px",
                  borderRadius: 6,
                  border: 0,
                  background: selectedType === "Egreso" ? "rgba(255, 94, 103, 0.2)" : "transparent",
                  color: selectedType === "Egreso" ? "var(--red)" : "var(--muted)",
                  fontSize: "0.78rem",
                  fontWeight: selectedType === "Egreso" ? 700 : 500,
                }}
              >
                Costos
              </button>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="table-wrap">
          <table className="data-table" style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left", fontSize: "0.78rem", color: "var(--muted)", textTransform: "uppercase" }}>
                <th style={{ padding: "10px 12px" }}>Fecha / Hora</th>
                <th style={{ padding: "10px 12px" }}>Tipo</th>
                <th style={{ padding: "10px 12px" }}>Concepto</th>
                <th style={{ padding: "10px 12px" }}>Descripción Original RIAL</th>
                <th style={{ padding: "10px 12px" }}>Cuenta</th>
                <th style={{ padding: "10px 12px", textAlign: "right" }}>Monto USD</th>
              </tr>
            </thead>
            <tbody>
              {movements.length > 0 ? (
                movements.map((m, idx) => {
                  const isSale = m.type === "Ingreso";
                  return (
                    <tr
                      key={`${m.date}-${m.time}-${idx}`}
                      style={{
                        borderBottom: "1px solid rgba(39, 68, 108, 0.25)",
                        fontSize: "0.85rem",
                      }}
                    >
                      <td style={{ padding: "10px 12px", whiteSpace: "nowrap" }}>
                        <span style={{ fontWeight: 650 }}>{m.date}</span>
                        {m.time ? <span style={{ color: "var(--muted)", marginLeft: 6, fontSize: "0.76rem" }}>{m.time}</span> : null}
                      </td>
                      <td style={{ padding: "10px 12px", whiteSpace: "nowrap" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "2px 8px",
                            borderRadius: 6,
                            fontSize: "0.74rem",
                            fontWeight: 700,
                            background: isSale ? "rgba(51, 230, 164, 0.12)" : "rgba(255, 94, 103, 0.12)",
                            color: isSale ? "var(--green)" : "var(--red)",
                            border: `1px solid ${isSale ? "rgba(51, 230, 164, 0.3)" : "rgba(255, 94, 103, 0.3)"}`,
                          }}
                        >
                          {isSale ? <ArrowDownLeft size={13} /> : <ArrowUpRight size={13} />}
                          {isSale ? "Venta" : "Costo"}
                        </span>
                      </td>
                      <td style={{ padding: "10px 12px", whiteSpace: "nowrap" }}>
                        <span style={{ fontWeight: 600, color: "var(--cyan)" }}>{m.subcategory || m.category}</span>
                      </td>
                      <td style={{ padding: "10px 12px", color: "var(--text)" }}>
                        {m.description}
                      </td>
                      <td style={{ padding: "10px 12px", whiteSpace: "nowrap", color: "var(--muted)", fontSize: "0.8rem" }}>
                        {m.account}
                      </td>
                      <td
                        style={{
                          padding: "10px 12px",
                          textAlign: "right",
                          fontWeight: 750,
                          color: isSale ? "var(--green)" : "var(--red)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {isSale ? "+" : "-"}{money(m.amount_usd)}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} style={{ padding: "30px 12px", textAlign: "center", color: "var(--muted)" }}>
                    No se encontraron movimientos comerciales con los filtros seleccionados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
