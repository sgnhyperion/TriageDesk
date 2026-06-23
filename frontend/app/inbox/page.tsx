// Ticket inbox. Owner: Member C.
// TODO(Member C): fetch listTickets() and render a real table linking to /tickets/[id].
import { listTickets } from "@/lib/api";
import Link from "next/link";

export default async function InboxPage() {
  let tickets: any[] = [];
  try {
    tickets = await listTickets();
  } catch {
    // backend not running yet — fall back to fixtures during parallel dev.
  }
  return (
    <main className="p-10">
      <h1 className="text-xl font-bold mb-4">Inbox</h1>
      <ul className="space-y-2">
        {tickets.map((t) => (
          <li key={t.id} className="border p-3 rounded">
            <Link href={`/tickets/${t.id}`} className="text-blue-600 underline">
              {t.id} — {t.subject}
            </Link>{" "}
            <span className="text-gray-500 text-sm">[{t.status}]</span>
          </li>
        ))}
        {tickets.length === 0 && (
          <li className="text-gray-500">No tickets (start the backend or load fixtures).</li>
        )}
      </ul>
    </main>
  );
}
