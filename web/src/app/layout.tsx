import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "자산 관리 시스템 1.6",
  description: "포트폴리오 자산 관리",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="antialiased">{children}</body>
    </html>
  );
}
