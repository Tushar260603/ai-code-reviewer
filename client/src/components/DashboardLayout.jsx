"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "../lib/api";
import { useAuth } from "./AuthGuard";

export default function DashboardLayout({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    try {
      setLoggingOut(true);
      await logout();
      router.replace("/login");
    } catch (err) {
      console.error("Logout failed:", err);
      router.replace("/login");
    } finally {
      setLoggingOut(false);
    }
  };

  const navLinks = [
    {
      name: "Dashboard",
      href: "/dashboard",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
      ),
    },
    {
      name: "Repositories",
      href: "/repositories",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
      ),
    },
    {
      name: "Metrics",
      href: "/metrics",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/dashboard" className="flex items-center gap-2 font-semibold text-slate-900 tracking-tight">
              <span className="w-6 h-6 rounded bg-slate-900 text-white flex items-center justify-center text-xs font-bold">
                AI
              </span>
              <span>Code Reviewer</span>
            </Link>
            <span className="hidden sm:inline-block text-slate-300 text-sm">|</span>
            <span className="hidden sm:inline-block text-xs font-medium text-slate-500 uppercase tracking-wider">
              Console
            </span>
          </div>

          <div className="flex items-center gap-4">
            {user && (
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                <span className="font-mono text-slate-900 font-medium">@{user.username}</span>
              </div>
            )}
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 px-3 py-1.5 rounded transition-colors"
            >
              {loggingOut ? "Signing out..." : "Sign out"}
            </button>
          </div>
        </div>
      </header>

      {/* Main Container with Sidebar */}
      <div className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 flex flex-col md:flex-row gap-6">
        {/* Left Sidebar Navigation */}
        <aside className="w-full md:w-52 shrink-0">
          <nav className="flex md:flex-col gap-1 bg-white md:bg-transparent p-2 md:p-0 rounded-lg md:rounded-none border md:border-0 border-slate-200">
            {navLinks.map((link) => {
              const isActive = pathname === link.href || (link.href !== "/dashboard" && pathname.startsWith(link.href));
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-md transition-colors ${
                    isActive
                      ? "bg-slate-900 text-white shadow-sm"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/80"
                  }`}
                >
                  {link.icon}
                  <span>{link.name}</span>
                </Link>
              );
            })}
          </nav>
        </aside>

        {/* Content Area */}
        <main className="flex-1 min-w-0">{children}</main>
      </div>
    </div>
  );
}
