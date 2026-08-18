import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Should Josh Ballard and Naïve talk?",
  description:
    "An application agent with one job, nine tools, and no access to anything it was not explicitly given.",
  robots: { index: true, follow: true },
};

const NAV: { href: string; label: string; cta?: boolean }[] = [
  { href: "/", label: "Ask" },
  { href: "/fit", label: "Fit" },
  { href: "/evidence", label: "Evidence" },
  { href: "/architecture", label: "Architecture" },
  { href: "/red-team", label: "Red team" },
  { href: "/talk", label: "Talk", cta: true },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;1,8..60,400&display=swap"
        />
      </head>
      <body>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-raised focus:px-4 focus:py-2 focus:text-ink"
        >
          Skip to content
        </a>

        <header className="sticky top-0 z-30 border-b border-rule bg-ground/95 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center gap-1 px-5">
            <Link
              href="/"
              className="mr-4 py-3.5 font-mono text-[11px] tracking-[0.16em] text-ink no-underline"
            >
              APPLICATION&nbsp;AGENT
            </Link>
            <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    item.cta
                      ? "ml-auto whitespace-nowrap rounded-[3px] border border-supported/40 px-3 py-1.5 text-[13px] text-supported no-underline transition-colors hover:bg-supported/10"
                      : "whitespace-nowrap px-3 py-3.5 text-[13px] text-muted no-underline transition-colors hover:text-ink"
                  }
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>

        <main id="main">{children}</main>

        <footer className="mt-24 border-t border-rule">
          <div className="mx-auto max-w-5xl px-5 py-10">
            <p className="label mb-3">Built by Josh Ballard</p>
            <p className="max-w-[60ch] text-[13.5px] text-muted">
              No analytics, no tracking, no third-party scripts. Your questions are not
              stored and not logged. Someone poking at a security demo should not be
              tracked, and saying so is part of the point.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
