// Supabase browser client (auth + session). Owner: Member C.
//
// Lazy + null-safe: when the project isn't configured (no env keys, or the
// .env.local.example placeholders are still in place) we run in "mock mode"
// so the whole UI stays demoable without a real Supabase project.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Treat the example placeholders as "not configured".
const PLACEHOLDERS = ["https://your-project.supabase.co", "your-anon-key"];

export const hasSupabaseKeys: boolean =
  !!URL &&
  !!ANON &&
  !PLACEHOLDERS.includes(URL) &&
  !PLACEHOLDERS.includes(ANON);

let _client: SupabaseClient | null = null;

/** Returns the Supabase client, or null when running in mock mode. */
export function getSupabase(): SupabaseClient | null {
  if (!hasSupabaseKeys) return null;
  if (!_client) _client = createClient(URL!, ANON!);
  return _client;
}
