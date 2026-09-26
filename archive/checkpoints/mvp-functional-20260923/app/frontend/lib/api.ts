const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000/api";

export async function api<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function money(value: number | null | undefined) {
  return `$${Number(value ?? 0).toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function pct(value: number | null | undefined) {
  return `${(Number(value ?? 0) * 100).toLocaleString("es-VE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}
