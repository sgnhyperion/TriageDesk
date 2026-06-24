"use client";
// Shown when running without Supabase keys (and/or backend) — i.e. demo mode.
// Owner: Member C.
export function MockModeBanner() {
  return (
    <div className="bg-amber-50 px-6 py-1.5 text-center text-xs text-amber-800">
      Demo mode — no Supabase keys detected. Auth is mocked; API reads fall back
      to sample fixtures when the backend is offline.
    </div>
  );
}
