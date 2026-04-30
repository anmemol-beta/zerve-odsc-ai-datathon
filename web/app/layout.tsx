import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/Providers";

export const metadata: Metadata = {
  title: "Zerve Canvas · Live",
  description:
    "ODSC × Zerve AI Datathon — a live mirror of the funnel + upgrade-prediction canvas, fetched in real time from the deployed FastAPI.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
