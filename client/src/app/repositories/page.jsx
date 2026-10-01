"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import AuthGuard, { useAuth } from "../../components/AuthGuard";
import DashboardLayout from "../../components/DashboardLayout";
import { getRepos, connectRepo, disconnectRepo } from "../../lib/api";

function RepositoriesContent() {
  const { user } = useAuth();
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState({});
  const [search, setSearch] = useState("");
  const [statusMessage, setStatusMessage] = useState(null);

  const fetchRepositories = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getRepos();
      setRepos(Array.isArray(data.repos) ? data.repos : []);
    } catch (err) {
      console.error("Failed to load repositories:", err);
      const msg = err.response?.data?.message || "Failed to load repositories. Please ensure you are logged in.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRepositories();
  }, []);

  const handleToggle = async (repoFullName, currentlyConnected) => {
    setActionLoading((prev) => ({ ...prev, [repoFullName]: true }));
    setStatusMessage(null);

    try {
      if (currentlyConnected) {
        await disconnectRepo(repoFullName);
        setRepos((prev) =>
          prev.map((r) => (r.fullName === repoFullName ? { ...r, isConnected: false } : r))
        );
        setStatusMessage({ type: "success", text: `Disconnected ${repoFullName}` });
      } else {
        const res = await connectRepo(repoFullName);
        setRepos((prev) =>
          prev.map((r) => (r.fullName === repoFullName ? { ...r, isConnected: true } : r))
        );
        setStatusMessage({ type: "success", text: res.message || `Connected ${repoFullName}!` });
      }
    } catch (err) {
      const msg = err.response?.data?.message || err.message || "Action failed";
      setStatusMessage({ type: "error", text: msg });
    } finally {
      setActionLoading((prev) => ({ ...prev, [repoFullName]: false }));
    }
  };

  const filteredRepos = repos.filter((r) =>
    r.fullName.toLowerCase().includes(search.toLowerCase())
  );

  const connectedCount = repos.filter((r) => r.isConnected).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">GitHub Repositories</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Connect repositories to automatically receive AI reviews on pull requests.
          </p>
        </div>
        <button
          onClick={fetchRepositories}
          disabled={loading}
          className="self-start text-xs text-slate-600 hover:text-slate-900 font-medium border border-slate-200 px-3 py-1.5 rounded hover:bg-slate-100 transition-colors"
        >
          {loading ? "Refreshing..." : "Sync from GitHub"}
        </button>
      </div>

      {/* Notification Toast */}
      {statusMessage && (
        <div
          className={`p-3 rounded-md text-xs border flex items-center justify-between ${
            statusMessage.type === "success"
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : "bg-red-50 text-red-800 border-red-200"
          }`}
        >
          <span>{statusMessage.text}</span>
          <button
            onClick={() => setStatusMessage(null)}
            className="text-slate-400 hover:text-slate-700 ml-2"
          >
            ✕
          </button>
        </div>
      )}

      {/* Overview Stats & Search */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span className="font-semibold text-slate-800">{connectedCount}</span>
            <span className="text-slate-500">Connected</span>
          </div>
          <div className="text-slate-300">|</div>
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-slate-800">{repos.length}</span>
            <span className="text-slate-500">Total Repositories</span>
          </div>
        </div>

        {/* Search Input */}
        <div className="w-full sm:w-64">
          <input
            type="text"
            placeholder="Search repositories..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full text-xs px-3 py-1.5 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-900"
          />
        </div>
      </div>

      {/* Repository List */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center gap-2">
            <div className="w-6 h-6 border-2 border-slate-300 border-t-slate-900 rounded-full animate-spin" />
            <p className="text-xs text-slate-500">Fetching your GitHub repositories...</p>
          </div>
        ) : error ? (
          <div className="py-12 text-center p-6">
            <p className="text-xs font-medium text-red-600 mb-2">{error}</p>
            <button
              onClick={fetchRepositories}
              className="text-xs bg-white text-slate-700 border border-slate-300 px-3 py-1.5 rounded font-medium hover:bg-slate-50"
            >
              Retry
            </button>
          </div>
        ) : filteredRepos.length === 0 ? (
          <div className="py-12 text-center border-dashed border-slate-200 m-4 rounded-md">
            <p className="text-xs font-medium text-slate-700">No repositories found.</p>
            <p className="text-[11px] text-slate-400 mt-1">
              {search ? "No matches for your search term." : "Make sure your GitHub account has repositories."}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredRepos.map((repo) => {
              const isWorking = actionLoading[repo.fullName];
              return (
                <div
                  key={repo.id || repo.fullName}
                  className="p-4 flex items-center justify-between gap-4 hover:bg-slate-50/60 transition-colors"
                >
                  <div className="min-w-0 flex items-center gap-3">
                    <svg
                      className="w-5 h-5 text-slate-400 shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                      />
                    </svg>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <a
                          href={repo.htmlUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="font-mono text-xs font-semibold text-slate-900 hover:text-blue-600 hover:underline truncate"
                        >
                          {repo.fullName}
                        </a>
                        {repo.private && (
                          <span className="text-[10px] uppercase font-semibold bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded border border-slate-200">
                            Private
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        Default branch: <span className="font-mono">{repo.defaultBranch || "main"}</span>
                      </p>
                    </div>
                  </div>

                  {/* Connect / Disconnect Action */}
                  <div className="flex items-center gap-3 shrink-0">
                    {repo.isConnected ? (
                      <>
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                          <span>✓</span> Active
                        </span>
                        <button
                          onClick={() => handleToggle(repo.fullName, true)}
                          disabled={isWorking}
                          className="text-xs text-red-600 hover:text-red-800 hover:bg-red-50 border border-red-200 px-2.5 py-1 rounded transition-colors disabled:opacity-50"
                        >
                          {isWorking ? "Removing..." : "Disconnect"}
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleToggle(repo.fullName, false)}
                        disabled={isWorking}
                        className="text-xs bg-slate-900 hover:bg-slate-800 text-white font-medium px-3 py-1 rounded shadow-sm transition-colors disabled:opacity-50"
                      >
                        {isWorking ? "Connecting..." : "Enable AI Review"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function RepositoriesPage() {
  return (
    <AuthGuard>
      <DashboardLayout>
        <RepositoriesContent />
      </DashboardLayout>
    </AuthGuard>
  );
}
