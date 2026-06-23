// Ticket detail + brain reasoning trace + HITL approval panel. Owner: Member C.
// TODO(Member C): build the full page —
//   1. show ticket + classification badges
//   2. "Run agent" button -> runTicket(id)
//   3. reasoning-trace view from getTrace(id)  (the standout demo feature)
//   4. draft + QA flags + approval panel calling submitDecision(id, action)
export default function TicketDetailPage({ params }: { params: { id: string } }) {
  return (
    <main className="p-10">
      <h1 className="text-xl font-bold mb-2">Ticket {params.id}</h1>
      <p className="text-gray-600">
        TODO(Member C): classification, reasoning trace, draft, and the
        Approve / Edit / Escalate / Reject panel.
      </p>
    </main>
  );
}
