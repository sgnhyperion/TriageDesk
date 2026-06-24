"use client";
// Auth context. Owner: Member C.
//
// Real mode (Supabase keys present): email/password sign-in; role comes from a
//   `profiles` row, defaulting to "agent".
// Mock mode (no keys): a fake session persisted in localStorage with a role
//   switcher, so the full app + role-gating is demoable without a project.
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { getSupabase, hasSupabaseKeys } from "@/lib/supabase";
import { setAuthToken } from "@/lib/api";
import type { Role } from "@/types/contract";

export interface AuthUser {
  email: string;
  role: Role;
}

interface AuthContextValue {
  user: AuthUser | null;
  role: Role | null;
  loading: boolean;
  mockMode: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signInMock: (role: Role) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const MOCK_KEY = "triagedesk.mockUser";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore session on mount.
  useEffect(() => {
    let active = true;
    async function init() {
      const sb = getSupabase();
      if (sb) {
        const { data } = await sb.auth.getSession();
        const session = data.session;
        if (session?.user && active) {
          setAuthToken(session.access_token);
          const role = await resolveRole(session.user);
          setUser({ email: session.user.email ?? "user", role });
        }
        // keep the api token in sync with future auth changes
        sb.auth.onAuthStateChange((_e, s) => {
          setAuthToken(s?.access_token ?? null);
        });
      } else {
        const raw =
          typeof window !== "undefined"
            ? window.localStorage.getItem(MOCK_KEY)
            : null;
        if (raw && active) setUser(JSON.parse(raw) as AuthUser);
      }
      if (active) setLoading(false);
    }
    init();
    return () => {
      active = false;
    };
  }, []);

  type WithMeta = {
    id: string;
    app_metadata?: Record<string, unknown>;
    user_metadata?: Record<string, unknown>;
  };

  function roleFromMetadata(u: WithMeta): Role | null {
    const r = (u.app_metadata?.role ?? u.user_metadata?.role) as string | undefined;
    return r === "admin" || r === "agent" ? r : null;
  }

  // Prefer the role carried in the Supabase session (app_metadata/user_metadata)
  // — set it in the dashboard and it works everywhere. Fall back to a profiles row.
  async function resolveRole(u: WithMeta): Promise<Role> {
    const fromMeta = roleFromMetadata(u);
    if (fromMeta) return fromMeta;
    const sb = getSupabase();
    if (!sb) return "agent";
    const { data } = await sb.from("profiles").select("role").eq("id", u.id).single();
    return (data?.role as Role) ?? "agent";
  }

  async function signIn(email: string, password: string) {
    const sb = getSupabase();
    if (!sb) throw new Error("Supabase not configured — use mock sign-in.");
    const { data, error } = await sb.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
    setAuthToken(data.session?.access_token ?? null);
    const role = data.user ? await resolveRole(data.user) : "agent";
    setUser({ email: data.user?.email ?? email, role });
  }

  function signInMock(role: Role) {
    const u: AuthUser = { email: `${role}@triagedesk.demo`, role };
    window.localStorage.setItem(MOCK_KEY, JSON.stringify(u));
    setUser(u);
  }

  async function signOut() {
    const sb = getSupabase();
    if (sb) await sb.auth.signOut();
    else window.localStorage.removeItem(MOCK_KEY);
    setAuthToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        role: user?.role ?? null,
        loading,
        mockMode: !hasSupabaseKeys,
        signIn,
        signInMock,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
