"use client";
// Top navigation bar. Owner: Member C.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { MockModeBanner } from "@/components/MockModeBanner";

function NavLink({ href, label }: { href: string; label: string }) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(href + "/");
  return (
    <Link
      href={href}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
        active
          ? "bg-slate-900 text-white"
          : "text-slate-600 hover:bg-slate-100"
      }`}
    >
      {label}
    </Link>
  );
}

export function AppHeader() {
  const { user, role, signOut, mockMode } = useAuth();

  return (
    <>
      {mockMode && <MockModeBanner />}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-slate-900 text-sm font-bold text-white">
              T
            </span>
            <span className="text-base font-semibold text-slate-900">
              TriageDesk
            </span>
          </Link>

          {user && (
            <nav className="flex items-center gap-1">
              <NavLink href="/inbox" label="Inbox" />
              {role === "admin" && <NavLink href="/admin" label="Admin" />}
            </nav>
          )}

          <div className="flex items-center gap-3">
            {user ? (
              <>
                <span className="hidden text-sm text-slate-500 sm:inline">
                  {user.email}
                  <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-slate-600">
                    {role}
                  </span>
                </span>
                <button
                  onClick={() => signOut()}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Sign out
                </button>
              </>
            ) : (
              <NavLink href="/login" label="Login" />
            )}
          </div>
        </div>
      </header>
    </>
  );
}
