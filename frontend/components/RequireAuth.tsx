"use client";
// Client-side route guards. Owner: Member C.
// (Real authorization is enforced server-side by Supabase RLS per schema.sql;
//  this is the UX gate.)
import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/types/contract";

export function RequireAuth({
  children,
  role,
}: {
  children: ReactNode;
  role?: Role;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="p-10 text-slate-500">Loading…</div>
    );
  }
  if (!user) return null; // redirecting

  if (role && user.role !== role) {
    return (
      <div className="mx-auto max-w-md p-10 text-center">
        <h1 className="text-lg font-semibold text-slate-900">
          Admins only
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          You&apos;re signed in as <b>{user.role}</b>. This area requires the{" "}
          <b>admin</b> role.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
