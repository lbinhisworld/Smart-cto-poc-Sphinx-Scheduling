import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Navigate, useLocation } from "react-router-dom";
import {
  applySkin,
  DEFAULT_SKIN,
  normalizeStoredSkin,
  type SkinId,
} from "../design/tokens";

export type RoleCode =
  | "GM"
  | "SALES_MGR"
  | "SALES"
  | "PMC"
  | "WH"
  | "FIN"
  | "HR"
  | "TEAM_LEADER";

type AuthState = {
  role: RoleCode;
  userName: string;
  skin: SkinId;
};

type AuthContextValue = {
  role: RoleCode | null;
  userName: string;
  skin: SkinId;
  isAuthenticated: boolean;
  setSession: (role: RoleCode, userName: string) => void;
  logout: () => void;
  headers: () => HeadersInit;
};

const STORAGE_KEY = "sphinx-demo-auth";
const SKIN_KEY = "sphinx-demo-skin";

const AuthContext = createContext<AuthContextValue | null>(null);

function loadStored(): Omit<AuthState, "skin"> | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as { role: RoleCode; userName: string };
    if (!p.role) return null;
    return p;
  } catch {
    return null;
  }
}

function readSkinFromStorage(): SkinId {
  const skin = normalizeStoredSkin(localStorage.getItem(SKIN_KEY));
  localStorage.setItem(SKIN_KEY, skin);
  applySkin(skin);
  return skin;
}

function readAuthState(): AuthState | null {
  const s = loadStored();
  const skin = readSkinFromStorage();
  if (!s) return null;
  return { ...s, skin };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState | null>(() => readAuthState());

  useEffect(() => {
    readSkinFromStorage();
  }, []);

  const setSession = useCallback((role: RoleCode, userName: string) => {
    const skin = readSkinFromStorage();
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ role, userName }));
    setState({ role, userName, skin });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setState(null);
  }, []);

  const headers = useCallback((): HeadersInit => {
    if (!state) return {};
    return { "X-Demo-Role": state.role };
  }, [state]);

  const value = useMemo(
    (): AuthContextValue => ({
      role: state?.role ?? null,
      userName: state?.userName ?? "",
      skin: state?.skin ?? DEFAULT_SKIN,
      isAuthenticated: state != null,
      setSession,
      logout,
      headers,
    }),
    [state, setSession, logout, headers],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside provider");
  return ctx;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const auth = useAuth();
  if (!auth.isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  return <>{children}</>;
}
