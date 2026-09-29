/**
 * Temporary in-memory session and saved-properties state.
 * Replaced by Supabase Auth and the `favorites` table in the backend step.
 */
import { createContext, useContext, useState, type ReactNode } from 'react';

export type Role = 'renter' | 'landlord' | 'agent';

export type User = {
  name: string;
  email: string;
  role: Role;
  agencyName?: string;
};

type Session = {
  user: User | null;
  signIn: (user: User) => void;
  signOut: () => void;
  savedIds: Set<string>;
  toggleSaved: (id: string) => void;
};

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());

  const toggleSaved = (id: string) =>
    setSavedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <SessionContext.Provider
      value={{ user, signIn: setUser, signOut: () => setUser(null), savedIds, toggleSaved }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used inside <SessionProvider>');
  return ctx;
}
