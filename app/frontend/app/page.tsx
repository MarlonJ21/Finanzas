"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  Calendar,
  Car,
  CheckCircle2,
  CreditCard,
  DollarSign,
  HeartPulse,
  Home,
  Laptop,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";
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

  if (status.isLoading || summary.isLoading || categories.isLoading) {
    return (
      <div className="page">
        <div className="skeleton" style={{ minHeight: 180 }} />
        <div className="skeleton" style={{ minHeight: 120 }} />
        <div className="skeleton" style={{ minHeight: 240 }} />
      </div>
    );
  }

  if (!summary.data || !categories.data) throw new Error("HOME_DATA_ERROR");

  const monthLabel = status.data?.current_month
    ? (() => {
        const d = new Date(status.data.current_month + "T00:00:00");
        const formatted = d.toLocaleDateString("es-VE", { month: "long", year: "numeric" });
        return formatted.charAt(0).toUpperCase() + formatted.slice(1);
      })()
    : "Mes actual";

  const cutDateStr = status.data?.cut_date ?? "";
  const cutDay = cutDateStr ? parseInt(cutDateStr.slice(-2), 10) : 15;
  const daysInMonth = 30;
  const daysRemaining = Math.max(daysInMonth - cutDay, 0);

  const consumed = summary.data.monthly_consumed_pct;
  const qExcess = Math.max(summary.data.biweekly_spend - summary.data.biweekly_budget, 0);
  const exceeded = categories.data.filter((row) => row.status === "EXCEEDED");
  const noBudget = categories.data.filter((row) => row.status === "NO_BUDGET");

  const alerts = [
    ...exceeded.slice(0, 3).map((row) => `${row.category} superó el presupuesto por ${money(Math.abs(row.available))}.`),
    ...noBudget.slice(0, 2).map((row) => `${row.category} registra gasto sin presupuesto asignado.`),
    ...(qExcess > 0 ? [`La quincena actual presenta un exceso de ${money(qExcess)}.`] : []),
    ...(status.data?.pending_classification ? [`${status.data.pending_classification} movimientos requieren clasificación.`] : []),
  ];

  const topCategories = [...categories.data].sort((a, b) => b.spent - a.spent).slice(0, 7);

  // Health diagnosis narrative
  let healthState: "good" | "warning" | "danger" = "good";
  let healthText = "Ritmo Saludable";
  let healthDesc = `Vas a buen ritmo. Te queda el ${pct(1 - consumed)} del presupuesto.`;

  if (consumed >= 1 || qExcess > 0) {
    healthState = "danger";
    healthText = "Presupuesto al Límite";
    healthDesc = `Has consumido el ${pct(consumed)} de tu presupuesto total este mes.`;
  } else if (consumed >= 0.75) {
    healthState = "warning";
    healthText = "Atención al Ritmo";
    healthDesc = `Has consumido el ${pct(consumed)}. Modera los gastos no esenciales.`;
  }

  const isPositiveBalance = summary.data.monthly_available >= 0;

  return (
    <section className="page">
      {/* 1. HERO STORY CARD: Tu pulso financiero en 3 segundos */}
      <div className="story-hero">
        <div className="story-header">
          <div className="story-period">
            <Calendar size={15} />
            <span>{monthLabel} · Corte {cutDateStr ? cutDateStr.slice(5) : "-"}</span>
          </div>
          <div className={`health-badge ${healthState}`}>
            {healthState === "good" ? <Sparkles size={13} /> : healthState === "warning" ? <AlertTriangle size={13} /> : <AlertCircle size={13} />}
            <span>{healthText}</span>
          </div>
        </div>

        <div className="story-main">
          <span className="story-label">Disponible para gastar</span>
          <div className={`story-amount ${isPositiveBalance ? "positive" : "negative"}`}>
            {isPositiveBalance ? "+" : ""}{money(summary.data.monthly_available)}
          </div>
          <span className="story-subtext">
            {healthDesc}
          </span>
        </div>

        <div className="story-progress-box">
          <div className="story-progress-stats">
            <span>
              <strong>{money(summary.data.personal_spend)}</strong> <span className="subtle">gastado</span>
            </span>
            <span>
              <span className="subtle">de </span><strong>{money(summary.data.monthly_budget)}</strong>
            </span>
          </div>

          <div className="story-progress-track">
            <div
              className={`story-progress-bar ${healthState}`}
              style={{ width: `${Math.max(0, Math.min(consumed * 100, 100))}%` }}
            />
          </div>

          <div className="story-narrative-note">
            <span>{pct(consumed)} consumido</span>
            <span>•</span>
            <span>{daysRemaining > 0 ? `${daysRemaining} días restantes` : "Cierre de mes"}</span>
          </div>
        </div>
      </div>

      {/* 2. BRÚJULA DE DECISIÓN RÁPIDA: Quincena & Gasto Seguro */}
      <div className="decision-grid">
        <div className="decision-card">
          <div className="decision-top">
            <span className="decision-title">Esta Quincena</span>
            <div className="decision-icon">
              <Wallet size={18} />
            </div>
          </div>
          <div className="decision-val">
            {money(summary.data.biweekly_available)}
          </div>
          <div className="decision-desc">
            {qExcess > 0 ? (
              <span className="red">Exceso {money(qExcess)}</span>
            ) : (
              <span>Gastado {money(summary.data.biweekly_spend)} de {money(summary.data.biweekly_budget)}</span>
            )}
          </div>
        </div>

        <div className="decision-card">
          <div className="decision-top">
            <span className="decision-title">Safe to Spend</span>
            <div className="decision-icon green">
              <ShieldCheck size={18} />
            </div>
          </div>
          <div className="decision-val green">
            {money(summary.data.safe_to_spend)}
          </div>
          <div className="decision-desc">
            <span>Límite seguro para gastar sin tocar tus ahorros ni cuotas fijas.</span>
          </div>
        </div>
      </div>

      {/* 3. DÓNDE SE ESTÁ YENDO TU DINERO (Top Gastos) */}
      <div>
        <div className="section-title-wrap">
          <h2 className="section-title">¿Dónde se fue tu dinero?</h2>
          <span className="subtle" style={{ fontSize: 12 }}>Top categorías</span>
        </div>

        <div className="category-stack">
          {topCategories.map((row) => {
            const Icon = getCategoryIcon(row.category, row.subcategory);
            const isOver = row.consumed_pct >= 1;
            const isNear = row.consumed_pct >= 0.8 && row.consumed_pct < 1;
            const barClass = isOver ? "var(--red)" : isNear ? "var(--yellow)" : "var(--cyan)";

            return (
              <div className="cat-card" key={`${row.category}-${row.subcategory}`}>
                <div className="cat-icon-wrap">
                  <Icon size={20} />
                </div>
                <div className="cat-details">
                  <div className="cat-header-line">
                    <span className="cat-name">{row.category}</span>
                    <span className="cat-spent">{money(row.spent)}</span>
                  </div>
                  <div className="cat-header-line">
                    <span className="cat-subname">{row.subcategory}</span>
                    <span className="cat-budget-line">de {money(row.budget)} ({pct(row.consumed_pct)})</span>
                  </div>
                  <div className="cat-bar-track">
                    <div
                      className="cat-bar-fill"
                      style={{
                        width: `${Math.max(0, Math.min(row.consumed_pct * 100, 100))}%`,
                        background: barClass,
                      }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. SALUD FINANCIERA & ALERTAS */}
      <div>
        <div className="section-title-wrap">
          <h2 className="section-title">Salud y Control</h2>
        </div>

        {alerts.length > 0 ? (
          <div style={{ display: "grid", gap: 10 }}>
            {alerts.map((alert) => (
              <div className="alert-item-card" key={alert}>
                <AlertTriangle size={18} style={{ color: "var(--yellow)", flexShrink: 0, marginTop: 1 }} />
                <span>{alert}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="health-positive-card">
            <CheckCircle2 size={24} style={{ color: "var(--green)", flexShrink: 0 }} />
            <div>
              <strong style={{ display: "block", fontSize: 14 }}>¡Todo bajo control!</strong>
              <span className="subtle">No tienes categorías sobregiradas ni movimientos pendientes de clasificar.</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function getCategoryIcon(category: string, subcategory: string) {
  const c = `${category} ${subcategory}`.toLowerCase();
  if (c.includes("aliment") || c.includes("comida") || c.includes("super") || c.includes("snack") || c.includes("cena")) return ShoppingBag;
  if (c.includes("movilidad") || c.includes("transporte") || c.includes("uber") || c.includes("gasolina") || c.includes("taxi") || c.includes("traslado")) return Car;
  if (c.includes("suscrip") || c.includes("herramienta") || c.includes("software") || c.includes("internet") || c.includes("streaming")) return Laptop;
  if (c.includes("salud") || c.includes("farmacia") || c.includes("medico") || c.includes("clinica")) return HeartPulse;
  if (c.includes("casa") || c.includes("hogar") || c.includes("alquiler") || c.includes("servicios")) return Home;
  if (c.includes("deuda") || c.includes("cashea") || c.includes("prestamo") || c.includes("tarjeta")) return CreditCard;
  return DollarSign;
}
