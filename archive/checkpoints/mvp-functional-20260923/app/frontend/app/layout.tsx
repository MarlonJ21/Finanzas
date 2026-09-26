import "./globals.css";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analisis Financiero",
  description: "MVP local para presupuesto y movimientos"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <main className="shell">
          <nav className="topnav">
            <strong>Analisis Financiero</strong>
            <div className="navlinks">
              <Link href="/">Home</Link>
              <Link href="/planner">Planner</Link>
              <Link href="/movements">Movimientos</Link>
              <Link href="/settings">Carga RIAL</Link>
            </div>
          </nav>
          {children}
        </main>
      </body>
    </html>
  );
}
