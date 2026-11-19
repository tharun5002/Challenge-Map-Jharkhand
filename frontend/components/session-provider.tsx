"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  clearSession,
  getSessionUser,
  login as loginRequest,
  registerAccount,
  saveSession,
  type ApiRole,
  type ApiUser,
} from "@/lib/api";

type SessionContextValue = {
  user: ApiUser | null;
  /** False until the stored session has been read on the client. */
  ready: boolean;
  signIn: (email: string, password: string, role: ApiRole) => Promise<ApiUser>;
  signUp: (input: {
    username: string;
    email: string;
    password: string;
    full_name: string;
    district: string | null;
  }) => Promise<ApiUser>;
  signOut: () => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  // Server and first client render agree on "signed out"; the stored session is
  // applied after mount so hydration never mismatches.
  const [user, setUser] = useState<ApiUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setUser(getSessionUser());
    setReady(true);

    const onStorage = (event: StorageEvent) => {
      if (event.key === null || event.key === "challengemap.user") {
        setUser(getSessionUser());
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const signIn = useCallback(async (
    email: string,
    password: string,
    role: ApiRole,
  ) => {
    const session = await loginRequest(email, password, role);
    saveSession(session);
    setUser(session.user);
    return session.user;
  }, []);

  const signUp = useCallback(
    async (input: {
      username: string;
      email: string;
      password: string;
      full_name: string;
      district: string | null;
    }) => {
      await registerAccount(input);
      // Registration returns the profile but not tokens, so sign in straight
      // away instead of bouncing the citizen through the form twice.
      return signIn(input.email, input.password, "citizen");
    },
    [signIn],
  );

  const signOut = useCallback(() => {
    clearSession();
    setUser(null);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({ user, ready, signIn, signUp, signOut }),
    [user, ready, signIn, signUp, signOut],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (value === null) {
    throw new Error("useSession must be used inside <SessionProvider>.");
  }
  return value;
}
