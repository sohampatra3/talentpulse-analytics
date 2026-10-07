import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TalentPulse Lab · Product Intelligence",
  description:
    "A product analytics and experimentation lab for job discovery. Explore synthetic behavioral data, compare AI search, and turn evidence into decisions.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{document.documentElement.dataset.theme=localStorage.getItem('talentpulse.theme.v1')||'light'}catch(e){document.documentElement.dataset.theme='light'}`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
