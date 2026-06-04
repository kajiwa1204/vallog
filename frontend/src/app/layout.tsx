import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vallog",
  description: "貢献可視化・報酬分配ツール",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
