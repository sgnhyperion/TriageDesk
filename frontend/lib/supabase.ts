// Supabase browser client (auth + session). Owner: Member C.
import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

// TODO(Member C): helpers for login/logout/session + role (agent/admin) checks.
