import "./globals.css";
import type { ReactNode } from "react";
import { AuthProvider } from "@/lib/auth";
import { AppHeader } from "@/components/AppHeader";

export const metadata = {
  title: "TriageDesk",
  description: "AI Support Desk — governed supervisor brain + human approval.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <AuthProvider>
          <AppHeader />
          <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
