"use client";
// Landing. Redirects authed users to /inbox; otherwise shows a brief intro.
import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/inbox");
  }, [loading, user, router]);

  return (
    <div className="mx-auto max-w-2xl py-10 text-center">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900">
        TriageDesk
      </h1>
      <p className="mt-3 text-slate-600">
        An AI support desk where a governed supervisor &ldquo;brain&rdquo;
        resolves tickets step by step — and a human approves every high-impact
        action.
      </p>
      <div className="mt-8">
        <Link
          href="/login"
          className="inline-block rounded-lg bg-slate-900 px-6 py-3 text-sm font-semibold text-white hover:bg-slate-800"
        >
          Sign in to start
        </Link>
      </div>
    </div>
  );
}
