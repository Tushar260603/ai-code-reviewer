"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getCurrentUser } from "../../lib/api";

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [checking, setChecking] = useState(true);
  const errorParam = searchParams.get("error");

  useEffect(() => {
    async function checkExistingAuth() {
      try {
        await getCurrentUser();
        // Already authenticated, redirect to dashboard
        router.replace("/dashboard");
      } catch (_) {
        setChecking(false);
      }
    }

    checkExistingAuth();
  }, [router]);

  const handleLogin = () => {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
    window.location.href = `${backendUrl}/api/auth/github`;
  };

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-5 h-5 border-2 border-slate-300 border-t-slate-800 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-sm bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
        {/* Brand */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-10 h-10 rounded-lg bg-slate-900 text-white flex items-center justify-center font-bold text-base mb-3 shadow-sm">
            AI
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            AI Code Reviewer
          </h1>
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
            Review your GitHub pull requests with multi-agent AI verification.
          </p>
        </div>

        {/* Error notification if redirected back with error */}
        {errorParam && (
          <div className="mb-5 p-3 rounded-md bg-red-50 border border-red-200 text-xs text-red-700 flex items-start gap-2">
            <svg className="w-4 h-4 text-red-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>
              Authentication failed. Please verify your GitHub authorization and try again.
            </span>
          </div>
        )}

        {/* Action */}
        <div className="space-y-4">
          <button
            onClick={handleLogin}
            className="w-full flex items-center justify-center gap-2.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold py-2.5 px-4 rounded-lg transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-900 focus:ring-offset-2"
          >
            {/* GitHub SVG Icon */}
            <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
            <span>Login with GitHub</span>
          </button>

          <p className="text-[11px] text-center text-slate-400">
            Secure authentication via GitHub OAuth &amp; HTTP-only cookies.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-50">
          <div className="w-5 h-5 border-2 border-slate-300 border-t-slate-800 rounded-full animate-spin" />
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
