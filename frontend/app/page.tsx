import Link from "next/link";

// Landing. TODO(Member C): redirect authenticated users straight to /inbox.
export default function Home() {
  return (
    <main className="p-10 space-y-4">
      <h1 className="text-2xl font-bold">TriageDesk</h1>
      <p className="text-gray-600">AI Support Desk — governed supervisor brain + human approval.</p>
      <nav className="flex gap-4 underline text-blue-600">
        <Link href="/login">Login</Link>
        <Link href="/inbox">Inbox</Link>
        <Link href="/admin">Admin</Link>
      </nav>
    </main>
  );
}
