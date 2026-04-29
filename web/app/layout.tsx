import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Zerve Funnel & Upgrade Predictor",
  description: "ODSC × Zerve AI Datathon — strict-nested funnel + leakage-safe upgrade model",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
