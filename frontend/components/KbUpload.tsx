"use client";
// Admin KB document upload + existing-docs list. Owner: Member C.
import { useEffect, useState } from "react";
import { listKbDocuments, uploadKbDoc } from "@/lib/api";
import type { KbDocument } from "@/types/contract";

export function KbUpload() {
  const [docs, setDocs] = useState<KbDocument[]>([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setDocs(await listKbDocuments());
  }
  useEffect(() => {
    refresh();
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setMsg(null);
    setError(null);
    try {
      const res = await uploadKbDoc(file, title || file.name);
      setMsg(`Indexed ${res.chunks_indexed} chunks (doc ${res.document_id}).`);
      setTitle("");
      setFile(null);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} — KB upload needs the live backend (Member B).`
          : "Upload failed"
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">Knowledge base</h2>
      <p className="mt-1 text-xs text-slate-500">
        Upload a help doc — it gets chunked, embedded, and made searchable for
        the brain&apos;s <code>retrieve_kb</code> tool.
      </p>

      <form onSubmit={onSubmit} className="mt-3 space-y-3">
        <input
          placeholder="Document title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />
        <input
          type="file"
          accept=".txt,.md,.pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-900 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-slate-800"
        />
        {msg && <p className="text-sm text-emerald-600">{msg}</p>}
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <button
          type="submit"
          disabled={busy || !file}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {busy ? "Uploading…" : "Upload & index"}
        </button>
      </form>

      <div className="mt-5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Indexed documents
        </h3>
        {docs.length === 0 ? (
          <p className="mt-2 text-sm text-slate-400">No documents yet.</p>
        ) : (
          <ul className="mt-2 divide-y divide-slate-100">
            {docs.map((d) => (
              <li
                key={d.id}
                className="flex items-center justify-between py-2 text-sm"
              >
                <span className="text-slate-700">{d.title}</span>
                <span className="text-xs text-slate-400">
                  {new Date(d.created_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
