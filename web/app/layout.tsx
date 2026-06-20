import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClearPath Estate",
  description: "Executor assistant dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

