import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  axes: ["opsz"],
});

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://diligence-os.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Diligence OS — AI due diligence for UK small-business acquisitions",
    template: "%s · Diligence OS",
  },
  description:
    "Diligence OS reads a seller's data room and hunts for where the numbers disagree — statutory accounts, VAT returns, bank statements and the P&L, reconciled line by line. Every finding cited to its source page.",
  keywords: [
    "due diligence",
    "UK business acquisition",
    "financial due diligence",
    "data room analysis",
    "VAT reconciliation",
    "Companies House checks",
    "red flag report",
    "SME acquisition",
  ],
  openGraph: {
    title: "Diligence OS — due diligence that reconciles, not summarises",
    description:
      "Upload a seller's data room. Get a cited Red Flag Report: every discrepancy traced to a source page, with the question to ask the seller and the SPA warranty to request.",
    url: siteUrl,
    siteName: "Diligence OS",
    locale: "en_GB",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Diligence OS — due diligence that reconciles, not summarises",
    description:
      "A cited Red Flag Report from the seller's own data room. Built for sub-£2M UK deals.",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en-GB"
      className={`${inter.variable} ${fraunces.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
