import React, { createContext, useContext, useEffect, useState } from "react";
import { getToken, clearToken } from "../api/client";
import { AuthUser } from "../api/auth";

interface AuthContextType {
  user: AuthUser | null;
  setUser: (user: AuthUser | null) => void;
  signOut: () => Promise<void>;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType>({} as AuthContextType);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // If a token exists on launch, mark as logged in (the API will reject it if expired).
    getToken().then((token) => {
      if (!token) setIsLoading(false);
      else {
        // We don't have the user object cached — just flag as authenticated.
        // The first API call will fail with 401 if the token is actually expired.
        setUser({ id: 0, username: "", role: "" });
        setIsLoading(false);
      }
    });
  }, []);

  async function signOut() {
    await clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, setUser, signOut, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
