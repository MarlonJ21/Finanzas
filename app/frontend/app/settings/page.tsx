"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  Filter,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Tag,
  Trash2,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  api,
  createClassificationRule,
  deleteClassificationRule,
  money,
  type ClassificationOptions,
  type CreateRulePayload,
  type PendingClassificationItem,
  type PendingClassificationResponse,
  type RulesResponse,
} from "../../lib/api";

export default function SettingsClassificationPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"pending" | "rules">("pending");
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Queries
  const pendingQuery = useQuery({
    queryKey: ["classification-pending"],
    queryFn: () => api<PendingClassificationResponse>("/classification/pending"),
  });

  const rulesQuery = useQuery({
    queryKey: ["classification-rules"],
    queryFn: () => api<RulesResponse>("/classification/rules"),
  });

  const optionsQuery = useQuery({
    queryKey: ["classification-options"],
    queryFn: () => api<ClassificationOptions>("/classification/options"),
  });

  // Modal form state
  const [formPattern, setFormPattern] = useState("");
  const [formCategory, setFormCategory] = useState("");
  const [formSubcategory, setFormSubcategory] = useState("");
  const [formDomain, setFormDomain] = useState("PERSONAL");
  const [formNature, setFormNature] = useState("EGRESO_CONSUMO");
  const [formTitular, setFormTitular] = useState("MARLON");
  const [formPriority, setFormPriority] = useState(10);
  const [selectedPendingItem, setSelectedPendingItem] = useState<PendingClassificationItem | null>(null);

  // Mutations
  const createRuleMutation = useMutation({
    mutationFn: (payload: CreateRulePayload) => createClassificationRule(payload),
    onSuccess: (data) => {
      setNotification({
        type: "success",
        message: `Regla ${data.rule_id} creada exitosamente. Movimientos pendientes restantes: ${data.pending_count_after}.`,
      });
      setRuleModalOpen(false);
      resetForm();
      queryClient.invalidateQueries();
    },
    onError: (err: any) => {
      setNotification({
        type: "error",
        message: err.message || "Error al crear la regla.",
      });
    },
  });

  const deleteRuleMutation = useMutation({
    mutationFn: (ruleId: string) => deleteClassificationRule(ruleId),
    onSuccess: (data) => {
      setNotification({
        type: "success",
        message: `Regla ${data.rule_id} eliminada. Finanzas recalculadas.`,
      });
      queryClient.invalidateQueries();
    },
    onError: (err: any) => {
      setNotification({
        type: "error",
        message: err.message || "Error al eliminar la regla.",
      });
    },
  });

  function resetForm() {
    setFormPattern("");
    setFormCategory("");
    setFormSubcategory("");
    setFormDomain("PERSONAL");
    setFormNature("EGRESO_CONSUMO");
    setFormTitular("MARLON");
    setFormPriority(10);
    setSelectedPendingItem(null);
  }

  function handleOpenCreateModal(item?: PendingClassificationItem) {
    if (item) {
      setSelectedPendingItem(item);
      setFormPattern(item.suggested_pattern || `(?i)${item.descripcion}`);
      // Default guesses based on Rial category if present
      if (item.tipo_rial.toLowerCase() === "ingreso") {
        setFormCategory("Ingresos");
        setFormSubcategory("Salario");
        setFormNature("INGRESOS_OPERATIVOS");
      } else {
        setFormCategory(item.categoria_rial || "Alimentación");
        setFormSubcategory(item.subcategoria_rial || "");
        setFormNature("EGRESO_CONSUMO");
      }
      setFormDomain("PERSONAL");
      setFormTitular("MARLON");
    } else {
      resetForm();
    }
    setRuleModalOpen(true);
  }

  const pendingItems = pendingQuery.data?.items ?? [];
  const rulesList = rulesQuery.data?.rules ?? [];
  const options = optionsQuery.data ?? {
    dominios: ["PERSONAL", "NEGOCIO", "PATRIMONIAL", "CONTROL"],
    categorias: [],
    subcategorias: {},
    titulares: ["MARLON", "ANILET", "PREMIADOSVE", "NO_APLICA"],
    naturalezas: ["EGRESO_CONSUMO", "INGRESOS_OPERATIVOS", "EGRESO_OPERATIVO", "PAGO_DEUDA"],
    tipos_rial: ["", "Egreso", "Ingreso"],
  };

  // Filter rules
  const filteredRules = useMemo(() => {
    if (!searchFilter.trim()) return rulesList;
    const term = searchFilter.toLowerCase();
    return rulesList.filter(
      (r) =>
        r.rule_id.toLowerCase().includes(term) ||
        r.pattern.toLowerCase().includes(term) ||
        r.categoria.toLowerCase().includes(term) ||
        r.subcategoria.toLowerCase().includes(term) ||
        r.dominio.toLowerCase().includes(term) ||
        r.naturaleza.toLowerCase().includes(term)
    );
  }, [rulesList, searchFilter]);

  // Live matching preview of pending items for current pattern
  const matchedPendingCount = useMemo(() => {
    if (!formPattern.trim()) return 0;
    try {
      const regex = new RegExp(formPattern.replace(/^\(\?i\)/, ""), "i");
      return pendingItems.filter((item) => regex.test(item.descripcion)).length;
    } catch {
      return 0;
    }
  }, [formPattern, pendingItems]);

  const availableSubcategories = options.subcategorias[formCategory] ?? [];

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Configuración & Automatización</p>
          <h1>Clasificación y Reglas</h1>
          <p className="subtle">
            Gestiona reglas automáticas para que cualquier gasto o ingreso similar se clasifique por sí solo al importar nuevos archivos.
          </p>
        </div>
        <div className="button-row">
          <button
            className="primary-button"
            onClick={() => handleOpenCreateModal()}
          >
            <Plus size={16} />
            Nueva Regla
          </button>
        </div>
      </div>

      {notification ? (
        <div
          className={`alert-item ${notification.type === "success" ? "green" : "red"}`}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: notification.type === "success" ? "rgba(51, 230, 164, 0.12)" : "rgba(255, 94, 103, 0.12)",
            borderLeft: `4px solid ${notification.type === "success" ? "var(--green)" : "var(--red)"}`,
            padding: "12px 16px",
            borderRadius: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {notification.type === "success" ? <CheckCircle2 size={18} className="green" /> : <AlertCircle size={18} className="red" />}
            <span>{notification.message}</span>
          </div>
          <button
            className="ghost-button"
            onClick={() => setNotification(null)}
            style={{ padding: 4, minHeight: "auto" }}
          >
            <X size={16} />
          </button>
        </div>
      ) : null}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 12, borderBottom: "1px solid rgba(39, 68, 108, .5)", paddingBottom: 10 }}>
        <button
          onClick={() => setActiveTab("pending")}
          className={`segment ${activeTab === "pending" ? "active" : ""}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 16px",
            cursor: "pointer",
            background: activeTab === "pending" ? "rgba(32, 215, 232, .15)" : "transparent",
            border: activeTab === "pending" ? "1px solid rgba(32, 215, 232, .4)" : "1px solid transparent",
            borderRadius: 8,
            color: activeTab === "pending" ? "var(--text)" : "var(--muted)",
            fontWeight: 700,
          }}
        >
          <AlertCircle size={16} className={pendingItems.length > 0 ? "yellow" : ""} />
          <span>Pendientes de Clasificación</span>
          {pendingItems.length > 0 ? (
            <span
              style={{
                background: "var(--yellow)",
                color: "#000",
                fontSize: "0.75rem",
                padding: "2px 7px",
                borderRadius: 999,
                fontWeight: 800,
              }}
            >
              {pendingItems.length}
            </span>
          ) : null}
        </button>

        <button
          onClick={() => setActiveTab("rules")}
          className={`segment ${activeTab === "rules" ? "active" : ""}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 16px",
            cursor: "pointer",
            background: activeTab === "rules" ? "rgba(32, 215, 232, .15)" : "transparent",
            border: activeTab === "rules" ? "1px solid rgba(32, 215, 232, .4)" : "1px solid transparent",
            borderRadius: 8,
            color: activeTab === "rules" ? "var(--text)" : "var(--muted)",
            fontWeight: 700,
          }}
        >
          <Filter size={16} />
          <span>Reglas Activas</span>
          <span
            style={{
              background: "rgba(120, 133, 158, 0.25)",
              color: "var(--text)",
              fontSize: "0.75rem",
              padding: "2px 7px",
              borderRadius: 999,
            }}
          >
            {rulesList.length}
          </span>
        </button>
      </div>

      {/* Tab 1: PENDING CLASSIFICATIONS */}
      {activeTab === "pending" && (
        <div className="surface panel-pad">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div>
              <h2>Movimientos sin clasificar ({pendingItems.length})</h2>
              <p className="subtle">
                Estos movimientos no coincidieron con ninguna regla existente. Puedes crear una regla directamente haciendo clic en <strong>Crear Regla</strong> para clasificar este y todos los futuros movimientos similares.
              </p>
            </div>
            <button
              className="secondary-button"
              onClick={() => {
                pendingQuery.refetch();
                queryClient.invalidateQueries({ queryKey: ["data-status"] });
              }}
              disabled={pendingQuery.isFetching}
            >
              <RefreshCw size={15} className={pendingQuery.isFetching ? "spin" : ""} />
              Actualizar
            </button>
          </div>

          {pendingItems.length === 0 ? (
            <div className="empty-state" style={{ padding: "40px 20px" }}>
              <CheckCircle2 size={44} className="green" style={{ marginBottom: 12 }} />
              <h3>¡Todo al día!</h3>
              <p className="subtle">No hay movimientos pendientes de clasificación en el historial actual.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Tipo</th>
                    <th>Descripción Original</th>
                    <th>Cuenta</th>
                    <th className="right">Monto (USD)</th>
                    <th className="right">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingItems.map((item) => (
                    <tr key={item.id}>
                      <td>{item.fecha}</td>
                      <td>
                        <span className={`status-chip ${item.tipo_rial.toLowerCase() === "ingreso" ? "status-within" : "status-exceeded"}`}>
                          {item.tipo_rial}
                        </span>
                      </td>
                      <td style={{ fontWeight: 600, maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis" }}>
                        {item.descripcion}
                      </td>
                      <td className="subtle">{item.cuenta || "-"}</td>
                      <td className="right" style={{ fontWeight: 700 }}>
                        {money(item.monto_usd)}
                      </td>
                      <td className="right">
                        <button
                          className="primary-button"
                          style={{ minHeight: 32, padding: "0 12px", fontSize: "0.82rem" }}
                          onClick={() => handleOpenCreateModal(item)}
                        >
                          <Sparkles size={14} />
                          Crear Regla
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: ACTIVE RULES */}
      {activeTab === "rules" && (
        <div className="surface panel-pad">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
            <div>
              <h2>Reglas de Clasificación ({filteredRules.length})</h2>
              <p className="subtle">
                Reglas evaluadas por orden de prioridad (menor número = mayor prioridad). Coinciden por expresión regular en la descripción.
              </p>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <div style={{ position: "relative", minWidth: 260 }}>
                <Search size={16} style={{ position: "absolute", left: 10, top: 12, color: "var(--muted)" }} />
                <input
                  type="text"
                  placeholder="Buscar regla, categoría, patrón..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  style={{
                    width: "100%",
                    minHeight: 38,
                    padding: "0 12px 0 34px",
                    borderRadius: 8,
                    border: "1px solid var(--border)",
                    background: "rgba(8, 21, 46, 0.5)",
                    color: "var(--text)",
                  }}
                />
              </div>
            </div>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Prio</th>
                  <th>Patrón (Regex)</th>
                  <th>Categoría</th>
                  <th>Subcategoría</th>
                  <th>Dominio</th>
                  <th>Naturaleza</th>
                  <th>Titular</th>
                  <th className="right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filteredRules.map((rule) => (
                  <tr key={rule.rule_id}>
                    <td>
                      <code style={{ color: "var(--cyan)", fontWeight: 700 }}>{rule.rule_id}</code>
                    </td>
                    <td className="subtle">{rule.priority}</td>
                    <td>
                      <code
                        style={{
                          background: "rgba(32, 215, 232, 0.08)",
                          padding: "3px 6px",
                          borderRadius: 4,
                          fontSize: "0.82rem",
                          color: "#7dd3fc",
                          maxWidth: 240,
                          display: "inline-block",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                        title={rule.pattern}
                      >
                        {rule.pattern}
                      </code>
                    </td>
                    <td style={{ fontWeight: 600 }}>{rule.categoria}</td>
                    <td className="subtle">{rule.subcategoria || "-"}</td>
                    <td>
                      <span className="context-pill" style={{ minHeight: 24, fontSize: "0.75rem", padding: "0 8px" }}>
                        {rule.dominio}
                      </span>
                    </td>
                    <td className="subtle" style={{ fontSize: "0.8rem" }}>{rule.naturaleza}</td>
                    <td className="subtle">{rule.titular}</td>
                    <td className="right">
                      <button
                        className="ghost-button"
                        style={{ color: "var(--red)", padding: "6px" }}
                        title="Eliminar regla"
                        disabled={deleteRuleMutation.isPending}
                        onClick={() => {
                          if (window.confirm(`¿Estás seguro de eliminar la regla ${rule.rule_id} (${rule.categoria})?`)) {
                            deleteRuleMutation.mutate(rule.rule_id);
                          }
                        }}
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL: CREAR REGLA */}
      {ruleModalOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: 640 }}>
            <div className="modal-header">
              <div>
                <p className="eyebrow">Automatización de Gastos</p>
                <h1>{selectedPendingItem ? "Crear Regla desde Movimiento" : "Nueva Regla de Clasificación"}</h1>
                <p className="subtle">
                  Define el patrón de coincidencia y cómo debe clasificarse automáticamente.
                </p>
              </div>
              <button
                className="ghost-button"
                onClick={() => setRuleModalOpen(false)}
                aria-label="Cerrar"
              >
                <X size={18} />
              </button>
            </div>

            <div className="panel-pad page">
              {selectedPendingItem ? (
                <div className="surface-lite panel-pad" style={{ background: "rgba(32, 215, 232, 0.05)" }}>
                  <div className="metric-label">Movimiento de referencia:</div>
                  <strong style={{ fontSize: "1.05rem" }}>{selectedPendingItem.descripcion}</strong>
                  <div style={{ display: "flex", gap: 14, marginTop: 6, fontSize: "0.85rem" }} className="subtle">
                    <span>Fecha: {selectedPendingItem.fecha}</span>
                    <span>Monto: {money(selectedPendingItem.monto_usd)}</span>
                    <span>Cuenta: {selectedPendingItem.cuenta}</span>
                  </div>
                </div>
              ) : null}

              <div className="field">
                <label>
                  Patrón de Búsqueda (Regex o Palabras Clave)
                  <span className="subtle" style={{ fontWeight: 400, marginLeft: 8 }}>
                    Usa <code>(?i)palabra1|palabra2</code> para ignorar mayúsculas/minúsculas.
                  </span>
                </label>
                <input
                  type="text"
                  value={formPattern}
                  onChange={(e) => setFormPattern(e.target.value)}
                  placeholder="Ej: (?i)bruno|veterinaria"
                  style={{ fontFamily: "monospace" }}
                />
                {matchedPendingCount > 0 ? (
                  <div style={{ fontSize: "0.8rem", color: "var(--green)", marginTop: 4, display: "flex", alignItems: "center", gap: 6 }}>
                    <Sparkles size={14} />
                    Esta regla clasificará {matchedPendingCount} movimiento{matchedPendingCount > 1 ? "s" : ""} pendiente{matchedPendingCount > 1 ? "s" : ""} de inmediato.
                  </div>
                ) : null}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="field">
                  <label>Categoría</label>
                  <select
                    value={formCategory}
                    onChange={(e) => {
                      setFormCategory(e.target.value);
                      setFormSubcategory("");
                    }}
                  >
                    <option value="">-- Seleccionar Categoría --</option>
                    {options.categorias.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label>Subcategoría</label>
                  {availableSubcategories.length > 0 ? (
                    <select
                      value={formSubcategory}
                      onChange={(e) => setFormSubcategory(e.target.value)}
                    >
                      <option value="">(Ninguna / General)</option>
                      {availableSubcategories.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      placeholder="Opcional (ej: Medicamentos)"
                      value={formSubcategory}
                      onChange={(e) => setFormSubcategory(e.target.value)}
                    />
                  )}
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="field">
                  <label>Dominio</label>
                  <select
                    value={formDomain}
                    onChange={(e) => setFormDomain(e.target.value)}
                  >
                    {options.dominios.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label>Titular</label>
                  <select
                    value={formTitular}
                    onChange={(e) => setFormTitular(e.target.value)}
                  >
                    {options.titulares.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="field">
                  <label>Naturaleza Financiera</label>
                  <select
                    value={formNature}
                    onChange={(e) => setFormNature(e.target.value)}
                  >
                    {options.naturalezas.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label>Prioridad de Regla</label>
                  <input
                    type="number"
                    min={1}
                    max={99}
                    value={formPriority}
                    onChange={(e) => setFormPriority(Number(e.target.value))}
                  />
                </div>
              </div>

              <div className="button-row" style={{ marginTop: 14 }}>
                <button
                  className="secondary-button"
                  onClick={() => setRuleModalOpen(false)}
                  disabled={createRuleMutation.isPending}
                >
                  Cancelar
                </button>
                <button
                  className="primary-button"
                  disabled={!formPattern.trim() || !formCategory.trim() || createRuleMutation.isPending}
                  onClick={() => {
                    createRuleMutation.mutate({
                      pattern: formPattern.trim(),
                      categoria: formCategory.trim(),
                      subcategoria: formSubcategory.trim(),
                      dominio: formDomain,
                      naturaleza: formNature,
                      titular: formTitular,
                      priority: formPriority,
                    });
                  }}
                >
                  {createRuleMutation.isPending ? (
                    <>
                      <RefreshCw size={16} className="spin" />
                      Guardando y recalculando...
                    </>
                  ) : (
                    <>
                      <Tag size={16} />
                      Guardar Regla y Clasificar
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
