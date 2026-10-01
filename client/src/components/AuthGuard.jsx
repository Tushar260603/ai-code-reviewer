"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser } from "../lib/api";

const AuthContext = createContext({
  user: null,
  loading: true,
});

export const useAuth = () => useContext(AuthContext);

/**
 * AuthGuard ensures client pages are only accessible by authenticated users.
 * Automatically checks session via GET /api/auth/me with HTTP-only cookie credentials.
 */
export default function AuthGuard({ children }) {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function checkAuth() {
      try {
        const userData = await getCurrentUser();
        if (isMounted) {
          setUser(userData);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setUser(null);
          setLoading(false);
          router.replace("/login");
        }
      }
    }

    checkAuth();

    return () => {
      isMounted = false;
    };
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-slate-300 border-t-slate-800 rounded-full animate-spin" />
          <p className="text-xs font-medium text-slate-500">Checking authentication...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null; // Will redirect via router.replace
  }

  return (
    <AuthContext.Provider value={{ user, loading }}>
      {children}
    </AuthContext.Provider>
  );
}
