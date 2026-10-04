"use client";

import React, { useState } from "react";
import { X, RefreshCw, CheckCircle2, Sliders, Globe, ShieldCheck } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getFxRates, updateFxConfig, syncFxRates, type FxRatesResponse } from "../../lib/api";

type FxConfigModalProps = {
  onClose: () => void;
};

export default function FxConfigModal({ onClose }: FxConfigModalProps) {
  const queryClient = useQueryClient();
  const { data: fxData, isLoading } = useQuery<FxRatesResponse>({
    queryKey: ["fx-rates"],
    queryFn: getFxRates,
  });

  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [manualRate, setManualRate] = useState<string>("976.14");
  const [initialized, setInitialized] = useState(false);

  // Sync state with fetched data once loaded
  if (fxData && !initialized) {
    setMode(fxData.mode || "auto");
    setManualRate(String(fxData.manual_rate || fxData.rate_usdt || "976.14"));
    setInitialized(true);
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const parsed = parseFloat(manualRate);
      return updateFxConfig({
        mode,
        manual_rate: !isNaN(parsed) && parsed > 0 ? parsed : undefined,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["fx-rates"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      onClose();
    },
  });

  const syncMutation = useMutation({
    mutationFn: syncFxRates,
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ["fx-rates"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      if (updated.live_rate) {
        setManualRate(String(updated.live_rate));
      }
    },
  });

  const bcv = fxData?.rate_bcv ?? 871.37;
  const usdt = mode === "auto" ? (fxData?.rate_usdt ?? 976.0) : (parseFloat(manualRate) || fxData?.rate_usdt || 976.14);
  const spread = bcv > 0 ? (((usdt - bcv) / bcv) * 100).toFixed(1) : "0.0";

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal fx-modal">
        <div className="sheet-handle" />
        <div className="modal-header">
          <div>
            <p className="eyebrow">Divisas y Tipo de Cambio</p>
            <h1>Tasa Binance USDT / VES</h1>
            <p className="subtle">Configura si la tasa Binance se sincroniza automáticamente vía P2P o de forma manual.</p>
          </div>
          <button className="ghost-button" aria-label="Cerrar" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="panel-pad page">
          {/* Tarjetas comparativas de tasas */}
          <div className="fx-rates-cards">
            <div className="fx-rate-card bcv">
              <span className="fx-card-title">🏛️ BCV Oficial</span>
              <strong className="fx-card-val">{bcv.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Bs</strong>
              <span className="fx-card-sub">Extraída de movimientos</span>
            </div>

            <div className="fx-rate-card usdt">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="fx-card-title">🟡 Binance USDT</span>
                <span className="fx-spread-badge">+{spread}%</span>
              </div>
              <strong className="fx-card-val text-cyan">
                {usdt.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Bs
              </strong>
              <span className="fx-card-sub">
                {mode === "auto" ? "Sincronizado vía Binance P2P" : "Modo manual personalizado"}
              </span>
            </div>
          </div>

          {/* Selector de modo */}
          <div className="fx-mode-selector">
            <label
              className={`fx-mode-option ${mode === "auto" ? "active" : ""}`}
              onClick={() => setMode("auto")}
            >
              <div className="fx-mode-radio">
                <input
                  type="radio"
                  name="fx-mode"
                  checked={mode === "auto"}
                  onChange={() => setMode("auto")}
                />
              </div>
              <div className="fx-mode-info">
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Globe size={16} className="text-cyan" />
                  <strong>Automático (Binance P2P en vivo)</strong>
                  <span className="badge-recommend">Recomendado</span>
                </div>
                <p className="subtle">
                  Consulta de forma continua el precio promedio en el mercado P2P de Binance de compra de USDT con VES.
                </p>
                {fxData?.last_sync && (
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, fontSize: "0.8rem", color: "var(--muted)" }}>
                    <span>Último sync: {new Date(fxData.last_sync).toLocaleTimeString("es-VE")}</span>
                    <button
                      type="button"
                      className="ghost-button fx-sync-mini-btn"
                      disabled={syncMutation.isPending}
                      onClick={(e) => {
                        e.stopPropagation();
                        syncMutation.mutate();
                      }}
                    >
                      <RefreshCw size={13} className={syncMutation.isPending ? "spin-animate" : ""} />
                      <span>{syncMutation.isPending ? "Sincronizando..." : "Sincronizar ahora"}</span>
                    </button>
                  </div>
                )}
              </div>
            </label>

            <label
              className={`fx-mode-option ${mode === "manual" ? "active" : ""}`}
              onClick={() => setMode("manual")}
            >
              <div className="fx-mode-radio">
                <input
                  type="radio"
                  name="fx-mode"
                  checked={mode === "manual"}
                  onChange={() => setMode("manual")}
                />
              </div>
              <div className="fx-mode-info">
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Sliders size={16} className="text-yellow" />
                  <strong>Manual (Tasa fija personalizada)</strong>
                </div>
                <p className="subtle">
                  Fija un valor manual personalizado si deseas congelar la tasa o ingresar un monto específico.
                </p>

                {mode === "manual" && (
                  <div className="fx-manual-input-box" onClick={(e) => e.stopPropagation()}>
                    <label htmlFor="manual-rate-input" style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)" }}>
                      Valor de 1 USDT en Bolívares (Bs):
                    </label>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                      <input
                        id="manual-rate-input"
                        type="number"
                        step="0.01"
                        min="1"
                        className="number-input"
                        style={{ maxWidth: 200 }}
                        value={manualRate}
                        onChange={(e) => setManualRate(e.target.value)}
                        placeholder="Ej. 976.14"
                      />
                      <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}>Bs / USDT</span>
                    </div>
                  </div>
                )}
              </div>
            </label>
          </div>

          {/* Botones de acción */}
          <div className="button-row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
            <button className="secondary-button" onClick={onClose} disabled={saveMutation.isPending}>
              Cancelar
            </button>
            <button
              className="primary-button"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || (mode === "manual" && (!parseFloat(manualRate) || parseFloat(manualRate) <= 0))}
            >
              {saveMutation.isPending ? "Guardando..." : "Guardar configuración"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
