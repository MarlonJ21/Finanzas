"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000/api";

export default function SettingsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<object | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(path: string) {
    if (!file) return;
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
    setResult(await response.json());
    setBusy(false);
  }

  return (
    <section className="page grid two">
      <div className="panel">
        <h1 className="section-title">Carga RIAL</h1>
        <div className="controls">
          <input type="file" accept=".csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button disabled={!file || busy} onClick={() => upload("/import/rial/preview")}>Preview</button>
          <button disabled={!file || busy} onClick={() => upload("/import/rial/commit")}>Commit</button>
        </div>
        <p className="label">{file ? file.name : "Selecciona un CSV exportado de RIAL."}</p>
      </div>
      <div className="panel">
        <h2 className="section-title">Resultado</h2>
        <pre>{result ? JSON.stringify(result, null, 2) : "{}"}</pre>
      </div>
    </section>
  );
}
