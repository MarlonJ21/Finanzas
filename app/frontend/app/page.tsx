"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Banknote,
  Calendar,
  Car,
  CheckCircle2,
  ChevronRight,
  Coins,
  CreditCard,
  DollarSign,
  HeartPulse,
  Home,
  Info,
  Laptop,
  Scale,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { useState } from "react";
import { api, bs, money, pct, type Category, type DashboardSummary, type DataStatus } from "../lib/api";

export default function HomePage() {
  const [currencyMode, setCurrencyMode] = useState<"USD" | "VES">("USD");
  const [showExplanation, setShowExplanation] = useState(false);

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

  // Rich clickable alert objects
  const structuredAlerts: { category: string; message: string; subtext: string; type: "exceeded" | "no_budget" | "quincena" }[] = [
    ...exceeded.map((row) => ({
      category: row.category,
      message: `${row.category} superó el presupuesto por ${money(Math.abs(row.available))}`,
      subtext: `Gastaste ${money(row.spent)} de una meta de ${money(row.budget)}. Toca para ver movimientos.`,
      type: "exceeded" as const,
    })),
    ...noBudget.map((row) => ({
      category: row.category,
      message: `${row.category} registra gasto sin presupuesto`,
      subtext: `Se registraron ${money(row.spent)} sin presupuesto planificado. Toca para ver movimientos.`,
      type: "no_budget" as const,
    })),
    ...(qExcess > 0
      ? [
          {
            category: "Quincena",
            message: `Quincena actual con sobregiro de ${money(qExcess)}`,
            subtext: `Gastaste ${money(summary.data.biweekly_spend)} en esta quincena. Toca para auditar movimientos.`,
            type: "quincena" as const,
          },
        ]
      : []),
  ];

  const topCategories = [...categories.data].sort((a, b) => b.spent - a.spent).slice(0, 8);

  // FX Rates
  const rateBcv = summary.data.rate_bcv || 857.01;
  const rateUsdt = summary.data.rate_usdt || 960.05;
  const fxSpreadPct = rateBcv > 0 ? ((rateUsdt - rateBcv) / rateBcv) * 100 : 0;

  // Health diagnosis narrative
  let healthState: "good" | "warning" | "danger" = "good";
  let healthText = "Ritmo Saludable";
  let healthDesc = `Vas a buen ritmo. Te queda el ${pct(1 - consumed)} de tu presupuesto total.`;

  if (consumed >= 1 || qExcess > 0) {
    healthState = "danger";
    healthText = "Presupuesto al Límite";
    healthDesc = `Has consumido el ${pct(consumed)} de tu presupuesto mensual.`;
  } else if (consumed >= 0.75) {
    healthState = "warning";
    healthText = "Atención al Ritmo";
    healthDesc = `Has consumido el ${pct(consumed)}. Modera los gastos no esenciales para cerrar el mes.`;
  }

  const isPositiveBalance = summary.data.monthly_available >= 0;

  return (
    <section className="page">
      {/* 1. TASAS DE CAMBIO EN VENEZUELA (BCV vs USDT) */}
      <div className="surface-lite fx-rates-strip">
        <div className="fx-rates-left">
          <div className="fx-rate-item">
            <span className="fx-flag">🏛️ BCV</span>
            <strong>{rateBcv.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Bs</strong>
          </div>
          <div className="fx-divider" />
          <div className="fx-rate-item">
            <span className="fx-flag">🟡 USDT</span>
            <strong>{rateUsdt.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Bs</strong>
          </div>
          <span className="fx-spread-badge">+{fxSpreadPct.toFixed(1)}%</span>
        </div>
        <button
          className="fx-toggle-btn"
          onClick={() => setCurrencyMode((prev) => (prev === "USD" ? "VES" : "USD"))}
          title="Alternar vista en Bolívares o Dólares"
        >
          <Coins size={14} />
          <span>Ver en {currencyMode === "USD" ? "Bs." : "USD"}</span>
        </button>
      </div>

      {/* 2. HERO STORY CARD: Tu disponible protagonista */}
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
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="story-label">Disponible para el resto del mes</span>
            <button
              className="ghost-button"
              style={{ padding: 4, height: 26, fontSize: 11, gap: 4 }}
              onClick={() => setShowExplanation(!showExplanation)}
            >
              <Info size={14} />
              <span>¿Cómo se calcula?</span>
            </button>
          </div>

          <div className={`story-amount ${isPositiveBalance ? "positive" : "negative"}`}>
            {currencyMode === "USD" ? (
              <>
                {isPositiveBalance ? "+" : ""}{money(summary.data.monthly_available)}
              </>
            ) : (
              <>
                {isPositiveBalance ? "+" : ""}{bs(summary.data.monthly_available, rateBcv)}
              </>
            )}
          </div>

          {/* Conversión de tasas simultánea si está en modo VES o USD */}
          <div className="story-fx-conversions">
            <span>En BCV: <strong>{bs(summary.data.monthly_available, rateBcv)}</strong></span>
            <span>•</span>
            <span>En USDT: <strong>{bs(summary.data.monthly_available, rateUsdt)}</strong></span>
          </div>

          <span className="story-subtext">{healthDesc}</span>
        </div>

        {/* Modal/Banner explicativo si el usuario pulsa ¿Cómo se calcula? */}
        {showExplanation && (
          <div className="explanation-callout">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <strong>💡 Entendiendo tus números:</strong>
              <button className="ghost-button" style={{ padding: 2 }} onClick={() => setShowExplanation(false)}>✕</button>
            </div>
            <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 12, lineHeight: 1.5 }}>
              <li>
                <strong>Disponible del Mes ({money(summary.data.monthly_available)}):</strong> Es lo que te queda en total de tu presupuesto mensual ({money(summary.data.monthly_budget)} presupuesto menos {money(summary.data.personal_spend)} gastados).
              </li>
              <li>
                <strong>Esta Quincena ({money(summary.data.biweekly_available)} margen teórico):</strong> Asignado para la Quincena {summary.data.biweekly_period ?? 2} ({money(summary.data.biweekly_budget)}) menos lo gastado en estos 15 días ({money(summary.data.biweekly_spend)}).
              </li>
              <li>
                <strong>Safe to Spend / Gasto Seguro ({money(summary.data.safe_to_spend)}):</strong> Es lo que verdaderamente puedes gastar hoy con seguridad. Si en la 1ra quincena hubo sobregiro, tu gasto seguro no puede superar lo que te queda en el mes. Por eso está topado a <strong>{money(summary.data.safe_to_spend)}</strong>.
              </li>
            </ul>
          </div>
        )}

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

      {/* 3. BRÚJULA DE DECISIÓN RÁPIDA: Quincena & Gasto Seguro */}
      <div className="decision-grid">
        <div className="decision-card">
          <div className="decision-top">
            <span className="decision-title">Esta Quincena</span>
            <div className="decision-icon">
              <Wallet size={18} />
            </div>
          </div>
          <div className="decision-val">
            {currencyMode === "USD" ? money(summary.data.biweekly_available) : bs(summary.data.biweekly_available, rateBcv)}
          </div>
          <div className="decision-desc">
            {qExcess > 0 ? (
              <span className="red">Exceso de {money(qExcess)}</span>
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
            {currencyMode === "USD" ? money(summary.data.safe_to_spend) : bs(summary.data.safe_to_spend, rateBcv)}
          </div>
          <div className="decision-desc">
            <span>Gasto seguro real topado al saldo disponible del mes.</span>
          </div>
        </div>
      </div>

      {/* 4. DÓNDE SE ESTÁ YENDO TU DINERO (Con enlace interactivo a Movimientos) */}
      <div>
        <div className="section-title-wrap">
          <h2 className="section-title">¿Dónde se fue tu dinero?</h2>
          <span className="subtle" style={{ fontSize: 12 }}>Toca para ver detalle</span>
        </div>

        <div className="category-stack">
          {topCategories.map((row) => {
            const Icon = getCategoryIcon(row.category, row.subcategory);
            const isOver = row.consumed_pct >= 1;
            const isNear = row.consumed_pct >= 0.8 && row.consumed_pct < 1;
            const barClass = isOver ? "var(--red)" : isNear ? "var(--yellow)" : "var(--cyan)";

            return (
              <Link
                href={`/movements?category=${encodeURIComponent(row.category)}`}
                className="cat-card clickable-cat-card"
                key={`${row.category}-${row.subcategory}`}
                title={`Ver movimientos de ${row.category}`}
              >
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
                    <span className="cat-budget-line">
                      de {money(row.budget)} ({pct(row.consumed_pct)})
                    </span>
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
                <ChevronRight size={18} className="cat-chevron" />
              </Link>
            );
          })}
        </div>
      </div>

      {/* 5. SALUD FINANCIERA & ALERTAS CLICKEABLES */}
      <div>
        <div className="section-title-wrap">
          <h2 className="section-title">Alertas y Salud de tus Gastos</h2>
          <span className="subtle" style={{ fontSize: 12 }}>Toca para auditar</span>
        </div>

        {structuredAlerts.length > 0 ? (
          <div style={{ display: "grid", gap: 10 }}>
            {structuredAlerts.map((alert, idx) => (
              <Link
                href={alert.category === "Quincena" ? "/movements" : `/movements?category=${encodeURIComponent(alert.category)}`}
                className="alert-item-card clickable-alert"
                key={`${alert.category}-${idx}`}
                title="Toca para ver los movimientos de este gasto"
              >
                <AlertTriangle size={20} style={{ color: "var(--yellow)", flexShrink: 0, marginTop: 2 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong style={{ display: "block", color: "#ffffff", fontSize: 13.5 }}>{alert.message}</strong>
                  <span className="subtle" style={{ display: "block", fontSize: 12, marginTop: 2 }}>
                    {alert.subtext}
                  </span>
                </div>
                <ArrowRight size={16} style={{ color: "var(--cyan)", flexShrink: 0, alignSelf: "center" }} />
              </Link>
            ))}
          </div>
        ) : (
          <div className="health-positive-card">
            <CheckCircle2 size={24} style={{ color: "var(--green)", flexShrink: 0 }} />
            <div>
              <strong style={{ display: "block", fontSize: 14 }}>¡Todo bajo control este mes!</strong>
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
