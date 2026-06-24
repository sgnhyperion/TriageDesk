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
          const role = await fetchRole(session.user.id);
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

  async function fetchRole(userId: string): Promise<Role> {
    const sb = getSupabase();
    if (!sb) return "agent";
    const { data } = await sb
      .from("profiles")
      .select("role")
      .eq("id", userId)
      .single();
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
    const role = data.user ? await fetchRole(data.user.id) : "agent";
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
