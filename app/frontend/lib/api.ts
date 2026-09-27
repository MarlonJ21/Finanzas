import { snapshot } from "./snapshot";

export function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_BASE) return process.env.NEXT_PUBLIC_API_BASE;
  if (typeof window !== "undefined") {
    // In cloud deployment where frontend and backend are on the same origin (no port or port 8000):
    if (!window.location.port || window.location.port === "8000" || window.location.port === "443" || window.location.port === "80") {
      return "/api";
    }
    return `http://${window.location.hostname}:8000/api`;
  }
  return "http://127.0.0.1:8000/api";
}

export const API_BASE = "http://127.0.0.1:8000/api";

export async function api<T>(path: string): Promise<T> {
  const fallback = snapshotFor(path);
  try {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 6000);
    const res = await fetch(`${getApiBase()}${path}`, { cache: "no-store", signal: controller.signal });
    window.clearTimeout(timer);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json() as Promise<T>;
  } catch (err) {
    if (fallback !== undefined) {
      console.warn(`[API] Usando snapshot de contingencia para: ${path}`, err);
      return fallback as T;
    }
    throw new Error("API_UNAVAILABLE");
  }
}

export async function uploadRial(mode: "preview" | "commit", file: File): Promise<Record<string, any>> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${getApiBase()}/import/rial/${mode}`, { method: "POST", body: form });
  if (!res.ok) {
    let msg = `Error ${res.status} al procesar archivo`;
    try {
      const data = await res.json();
      if (data.errors && data.errors.length) {
        msg = data.errors.join(", ");
      } else if (data.detail) {
        msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      const text = await res.text().catch(() => "");
      if (text) msg = text;
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function createClassificationRule(payload: CreateRulePayload): Promise<{ status: string; rule_id: string; pending_count_after: number; message: string }> {
  const res = await fetch(`${getApiBase()}/classification/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "ERROR_CREATING_RULE");
  }
  return res.json();
}

export async function deleteClassificationRule(ruleId: string): Promise<{ status: string; rule_id: string; pending_count_after: number; message: string }> {
  const res = await fetch(`${getApiBase()}/classification/rules/${encodeURIComponent(ruleId)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "ERROR_DELETING_RULE");
  }
  return res.json();
}

function snapshotFor(path: string): unknown {
  if (path.startsWith("/data/status")) return snapshot.status;
  if (path.startsWith("/dashboard/summary")) return snapshot.dashboard;
  if (path.startsWith("/dashboard/categories")) return snapshot.categories;
  if (path.startsWith("/planner/summary")) {
    const scenario = new URLSearchParams(path.split("?")[1] ?? "").get("scenario") ?? "REALISTIC";
    return snapshot.planner[scenario as keyof typeof snapshot.planner] ?? snapshot.planner.REALISTIC;
  }
  if (path.startsWith("/planner/categories/")) {
    const id = path.split("/planner/categories/")[1]?.split("?")[0];
    const row = snapshot.plannerRows.find((item) => item.id_category === id);
    return row ? { ...row, confidence_reason: "Vista publicada con snapshot del ultimo calculo local disponible.", method: row.forecast_type } : undefined;
  }
  if (path.startsWith("/planner/categories")) return snapshot.plannerRows;
  if (path.startsWith("/movements")) return snapshot.movements;
  if (path.startsWith("/classification/pending")) return { total: 0, items: [] };
  if (path.startsWith("/classification/rules")) return { total: 0, rules: [] };
  if (path.startsWith("/classification/options")) {
    return {
      dominios: ["PERSONAL", "NEGOCIO", "PATRIMONIAL", "CONTROL"],
      categorias: ["Alimentación", "Suscripciones / Herramientas", "Movilidad", "Salud", "Ingresos", "PremiadosVE"],
      subcategorias: {},
      titulares: ["MARLON", "ANILET", "PREMIADOSVE", "NO_APLICA"],
      naturalezas: ["EGRESO_CONSUMO", "INGRESOS_OPERATIVOS", "EGRESO_OPERATIVO", "PAGO_DEUDA", "PUBLICIDAD"],
      tipos_rial: ["", "Egreso", "Ingreso", "Transferencia (salida)", "Transferencia (entrada)"],
    };
  }
  return undefined;
}

function shouldUseLocalApi() {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return (
    host === "127.0.0.1" ||
    host === "localhost" ||
    host.startsWith("192.168.") ||
    host.startsWith("10.") ||
    host.startsWith("172.") ||
    host.endsWith(".local")
  );
}

export function money(value: number | null | undefined) {
  const amount = Number(value ?? 0);
  const formatted = Math.abs(amount).toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${amount < 0 ? "-" : ""}$${formatted}`;
}

export function pct(value: number | null | undefined) {
  return `${(Number(value ?? 0) * 100).toLocaleString("es-VE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

export type DataStatus = {
  last_update: string | null;
  cut_date: string | null;
  current_month?: string | null;
  plan_month?: string | null;
  planning_enabled?: boolean;
  movement_count: number;
  exact_duplicates: number;
  possible_duplicates: number;
  missing_fx: number;
  pending_classification: number;
};

export type DashboardSummary = {
  income_sustainable: number;
  personal_spend: number;
  monthly_budget: number;
  monthly_available: number;
  monthly_consumed_pct: number;
  biweekly_spend: number;
  biweekly_budget: number;
  biweekly_available: number;
  safe_to_spend: number;
  salary_collected_biweekly: number;
};

export type Category = {
  category: string;
  subcategory: string;
  spent: number;
  budget: number;
  available: number;
  consumed_pct: number;
  status: string;
};

export type PlannerSummary = {
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
  scenario: string;
};

export type PlannerCategory = {
  id_category: string;
  category: string;
  subcategory: string;
  forecast_type: string;
  confidence: string;
  confidence_score: number;
  flexibility: string;
  is_essential: number;
  current_budget: number;
  current_mtd: number;
  previous_same_period: number;
  projected_close: number;
  forecast_next_month: number;
  suggested_budget: number;
  manual_budget: number | null;
  final_budget: number;
};

export type PlannerDetail = PlannerCategory & {
  historical_average: number;
  historical_median: number;
  previous_full_month: number;
  method: string;
  confidence_reason: string;
  scenario_factor: number;
  floor_usd: number;
  cap_usd: number;
};

export type Movement = {
  date: string;
  description: string;
  domain: string;
  category: string;
  subcategory: string;
  account: string;
  amount_usd: number;
  type: string;
};

export type MovementResponse = {
  total: number;
  limit: number;
  offset: number;
  items: Movement[];
};

export type PendingClassificationItem = {
  id: string;
  fecha: string;
  tipo_rial: string;
  categoria_rial: string;
  subcategoria_rial: string;
  descripcion: string;
  cuenta: string;
  monto_usd: number;
  monto_original: string;
  moneda: string;
  suggested_pattern: string;
};

export type PendingClassificationResponse = {
  total: number;
  items: PendingClassificationItem[];
};

export type CategoryRule = {
  rule_id: string;
  priority: number;
  tipo_rial: string;
  categoria_rial: string;
  subcategoria_rial: string;
  pattern: string;
  match_mode: string;
  dominio: string;
  categoria: string;
  subcategoria: string;
  titular: string;
  naturaleza: string;
  flags: Record<string, number>;
};

export type RulesResponse = {
  total: number;
  rules: CategoryRule[];
};

export type ClassificationOptions = {
  dominios: string[];
  categorias: string[];
  subcategorias: Record<string, string[]>;
  titulares: string[];
  naturalezas: string[];
  tipos_rial: string[];
};

export type CreateRulePayload = {
  pattern: string;
  dominio: string;
  categoria: string;
  subcategoria?: string;
  titular?: string;
  naturaleza?: string;
  tipo_rial?: string;
  priority?: number;
};

