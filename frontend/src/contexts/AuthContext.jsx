import { createContext, useContext, useEffect, useState } from "react";
import { getMe, getToken, clearToken } from "../services/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setReady(true);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setReady(true));
  }, []);

  const refreshUser = async () => {
    try {
      const u = await getMe();
      setUser(u);
    } catch {
      setUser(null);
      clearToken();
    }
  };

  const logout = () => {
    clearToken();
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{ user, ready, refreshUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
