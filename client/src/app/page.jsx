"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser } from "../lib/api";

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    async function determineRoute() {
      try {
        await getCurrentUser();
        router.replace("/dashboard");
      } catch (err) {
        router.replace("/login");
      }
    }

    determineRoute();
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="flex flex-col items-center gap-3">
        <div className="w-6 h-6 border-2 border-slate-300 border-t-slate-800 rounded-full animate-spin" />
        <p className="text-xs font-medium text-slate-500">Loading AI Code Reviewer...</p>
      </div>
    </div>
  );
}
