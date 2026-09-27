"use client";

export default function Error({ reset }: { reset: () => void }) {
  return (
    <div className="empty-state">
      <div>
        <h1>No se pudo cargar la vista</h1>
        <p className="subtle">La API local no respondio como se esperaba.</p>
        <button className="primary-button" onClick={reset}>Reintentar</button>
      </div>
    </div>
  );
}
