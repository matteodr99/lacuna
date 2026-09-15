import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SITE_URL } from "@/lib/site";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Lacuna — adaptive cloud certification practice",
    template: "%s — Lacuna",
  },
  description:
    "Practice questions for AWS, Azure and GCP certifications, focused on the granular details experienced engineers actually forget. Every question is checked against the official documentation before it reaches you.",
  openGraph: {
    type: "website",
    siteName: "Lacuna",
    url: "/",
    title: "Lacuna — the details you forget, not the concepts you know",
    description:
      "AWS SAA-C03 practice questions for experienced engineers, every claim checked against the official documentation.",
  },
  twitter: { card: "summary_large_image" },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
        <header className="border-b border-zinc-200 dark:border-zinc-800">
          <nav className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-4">
            <Link href="/" className="font-semibold tracking-tight">
              Lacuna
            </Link>
            <Link
              href="/weak-spots"
              className="text-sm text-zinc-600 underline-offset-4 hover:underline dark:text-zinc-400"
            >
              Weak spots
            </Link>
          </nav>
        </header>
        <main className="flex flex-1 flex-col">{children}</main>
        <footer className="border-t border-zinc-200 dark:border-zinc-800">
          <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-6 py-6 text-xs text-zinc-500 dark:text-zinc-400">
            <span>Lacuna — practice for the gaps, not the basics.</span>
            <a
              href="https://github.com/matteodr99/lacuna"
              className="underline-offset-4 hover:underline"
            >
              Source on GitHub
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
