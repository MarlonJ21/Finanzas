import "./globals.css";
import type { Metadata } from "next";
import { AppProviders } from "./providers";
import { AppShell } from "./components/AppShell";

export const metadata: Metadata = {
  title: "Finanzas",
  description: "Aplicacion financiera personal local"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <AppProviders>
          <AppShell>{children}</AppShell>
        </AppProviders>
      </body>
    </html>
  );
}
