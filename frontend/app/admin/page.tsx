"use client";
// Admin: KB upload + analytics dashboard. Owner: Member C. Admin-gated.
import { KbUpload } from "@/components/KbUpload";
import { AnalyticsCards } from "@/components/AnalyticsCards";
import { RequireAuth } from "@/components/RequireAuth";

function Admin() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Admin</h1>
        <p className="text-sm text-slate-500">
          Knowledge base management and support analytics.
        </p>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Analytics</h2>
        <AnalyticsCards />
      </section>

      <section>
        <KbUpload />
      </section>
    </div>
  );
}

export default function AdminPage() {
  return (
    <RequireAuth role="admin">
      <Admin />
    </RequireAuth>
  );
}
