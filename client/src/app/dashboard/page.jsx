"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import AuthGuard, { useAuth } from "../../components/AuthGuard";
import DashboardLayout from "../../components/DashboardLayout";
import { getReviews, triggerReview } from "../../lib/api";

function formatVerdict(verdict) {
  const norm = String(verdict || "").toLowerCase();
  switch (norm) {
    case "approve":
    case "approved":
      return {
        label: "Approved",
        badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
        icon: "✓",
      };
    case "request_changes":
      return {
        label: "Changes Requested",
        badge: "bg-red-50 text-red-700 border-red-200",
        icon: "✕",
      };
    case "comment":
    default:
      return {
        label: "Commented",
        badge: "bg-slate-100 text-slate-700 border-slate-200",
        icon: "💬",
      };
  }
}

function DashboardContent() {
  const { user } = useAuth();
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [triggeringPr, setTriggeringPr] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState("");
  const [prNumberInput, setPrNumberInput] = useState("1");
  const [triggerMessage, setTriggerMessage] = useState(null);

  const [pollingActive, setPollingActive] = useState(false);

  const fetchRecentReviews = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getReviews();
      setReviews(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to load reviews:", err);
      setError("Unable to load reviews.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecentReviews();
  }, []);

  // Auto-poll every 2.5s when a review is processing
  useEffect(() => {
    if (!pollingActive) return;
    const interval = setInterval(async () => {
      try {
        const data = await getReviews();
        const newReviews = Array.isArray(data) ? data : [];
        // Stop polling if we got a new review OR latest review changed/updated
        const hasNew = newReviews.length > reviews.length;
        const hasUpdated =
          newReviews.length > 0 &&
          reviews.length > 0 &&
          (newReviews[0].id !== reviews[0].id ||
            newReviews[0].createdAt !== reviews[0].createdAt ||
            newReviews[0].verdict !== reviews[0].verdict);

        if (hasNew || hasUpdated) {
          setReviews(newReviews);
          setPollingActive(false);
          setTriggerMessage({ type: "success", text: "✅ Review complete! Results are ready below." });
          clearInterval(interval);
        }
      } catch (_) {}
    }, 2500);

    // Stop polling after 45 seconds
    const timeout = setTimeout(() => {
      setPollingActive(false);
      clearInterval(interval);
      fetchRecentReviews();
    }, 45000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [pollingActive, reviews.length]);

  const handleManualTrigger = async (e) => {
    e.preventDefault();
    if (!selectedRepo || !prNumberInput) return;

    try {
      setTriggeringPr(true);
      setTriggerMessage(null);
      const res = await triggerReview(selectedRepo, prNumberInput);
      setModalOpen(false);
      // Server returns 202 immediately — review is running in background
      setTriggerMessage({
        type: "info",
        text: "⚙️ AI agents are analysing your code... Results will appear below in ~30–60 seconds.",
      });
      setPollingActive(true);
    } catch (err) {
      const msg = err.response?.data?.message || err.message || "Review trigger failed";
      setTriggerMessage({ type: "error", text: msg });
    } finally {
      setTriggeringPr(false);
    }
  };

  const connectedRepos = user?.connectedRepos || [];

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Dashboard</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Overview of connected repositories and automated pull request reviews.
        </p>
      </div>

      {/* Connected Repositories Section */}
      <section className="bg-white border border-slate-200 rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Connected Repositories</h2>
            <p className="text-xs text-slate-500">Repositories monitored for automated reviews</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500 font-mono">
              {connectedRepos.length} {connectedRepos.length === 1 ? "repo" : "repos"}
            </span>
            <Link
              href="/repositories"
              className="text-xs bg-slate-900 hover:bg-slate-800 text-white font-medium px-2.5 py-1 rounded transition-colors"
            >
              + Connect Repo
            </Link>
          </div>
        </div>

        {connectedRepos.length === 0 ? (
          <div className="py-6 text-center border border-dashed border-slate-200 rounded-md">
            <p className="text-xs text-slate-500">No repositories connected yet.</p>
            <p className="text-[11px] text-slate-400 mt-1 mb-3">
              Connect your repositories with 1-click to start automatic AI reviews.
            </p>
            <Link
              href="/repositories"
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 underline"
            >
              Go to Repositories →
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {connectedRepos.map((repo, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2.5 p-3 rounded-md border border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition-colors"
              >
                <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                <span className="font-mono text-xs text-slate-800 font-medium truncate">
                  {repo}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Trigger Status Notification */}
      {triggerMessage && (
        <div
          className={`p-3 rounded-md text-xs border flex items-center justify-between ${
            triggerMessage.type === "success"
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : triggerMessage.type === "info"
              ? "bg-blue-50 text-blue-800 border-blue-200"
              : "bg-red-50 text-red-800 border-red-200"
          }`}
        >
          <span className="flex items-center gap-2">
            {pollingActive && (
              <span className="w-3 h-3 border-2 border-blue-400 border-t-blue-700 rounded-full animate-spin inline-block" />
            )}
            {triggerMessage.text}
          </span>
          <button onClick={() => { setTriggerMessage(null); setPollingActive(false); }} className="text-slate-400 hover:text-slate-700 ml-2">
            ✕
          </button>
        </div>
      )}

      {/* Manual Trigger Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900">⚡ Trigger AI Code Review</h3>
              <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-slate-600 text-sm">
                ✕
              </button>
            </div>
            <form onSubmit={handleManualTrigger} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Repository</label>
                {connectedRepos.length > 0 ? (
                  <select
                    value={selectedRepo}
                    onChange={(e) => setSelectedRepo(e.target.value)}
                    className="w-full text-xs p-2 border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-900 font-mono"
                    required
                  >
                    <option value="">Select a repository...</option>
                    {connectedRepos.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    placeholder="e.g. owner/repo"
                    value={selectedRepo}
                    onChange={(e) => setSelectedRepo(e.target.value)}
                    className="w-full text-xs p-2 border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-900 font-mono"
                    required
                  />
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Pull Request Number</label>
                <input
                  type="number"
                  min="1"
                  placeholder="e.g. 1"
                  value={prNumberInput}
                  onChange={(e) => setPrNumberInput(e.target.value)}
                  className="w-full text-xs p-2 border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-900 font-mono"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="text-xs px-3 py-1.5 border border-slate-300 rounded text-slate-600 hover:bg-slate-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={triggeringPr}
                  className="text-xs px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded font-medium shadow-sm transition-colors disabled:opacity-50"
                >
                  {triggeringPr ? "Running AI Agents..." : "Start Review"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Recent Reviews Section */}
      <section className="bg-white border border-slate-200 rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Recent Reviews</h2>
            <p className="text-xs text-slate-500">Latest pull request evaluations</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (connectedRepos.length > 0 && !selectedRepo) {
                  setSelectedRepo(connectedRepos[0]);
                }
                setModalOpen(true);
              }}
              className="text-xs bg-slate-900 hover:bg-slate-800 text-white font-medium px-3 py-1 rounded transition-colors shadow-sm"
            >
              ⚡ Review PR Now
            </button>
            <button
              onClick={fetchRecentReviews}
              disabled={loading}
              className="text-xs text-slate-600 hover:text-slate-900 font-medium border border-slate-200 px-2.5 py-1 rounded hover:bg-slate-50 transition-colors"
            >
              {loading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="py-12 flex flex-col items-center justify-center gap-2">
            <div className="w-5 h-5 border-2 border-slate-300 border-t-slate-800 rounded-full animate-spin" />
            <p className="text-xs text-slate-500">Loading reviews...</p>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="py-8 text-center border border-red-200 bg-red-50/50 rounded-md">
            <p className="text-xs font-medium text-red-700">{error}</p>
            <button
              onClick={fetchRecentReviews}
              className="mt-3 text-xs bg-white text-slate-700 hover:text-slate-900 border border-slate-300 px-3 py-1.5 rounded font-medium shadow-sm transition-colors"
            >
              Try again
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && reviews.length === 0 && (
          <div className="py-12 text-center border border-dashed border-slate-200 rounded-md">
            <svg className="w-8 h-8 text-slate-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-xs font-medium text-slate-700">No reviews yet.</p>
            <p className="text-[11px] text-slate-400 mt-1 max-w-sm mx-auto">
              Once a GitHub pull request is opened or updated, your automated review history will appear here.
            </p>
          </div>
        )}

        {/* Reviews Table */}
        {!loading && !error && reviews.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold text-[11px]">
                  <th className="py-2.5 px-3">Repository</th>
                  <th className="py-2.5 px-3">PR</th>
                  <th className="py-2.5 px-3">Title</th>
                  <th className="py-2.5 px-3">Verdict</th>
                  <th className="py-2.5 px-3">Date</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-normal text-slate-700">
                {reviews.map((rev) => {
                  const v = formatVerdict(rev.verdict);
                  const prTargetId = rev.prId || rev.id;
                  const dateStr = rev.createdAt
                    ? new Date(rev.createdAt).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "—";

                  return (
                    <tr
                      key={rev.id}
                      className="hover:bg-slate-50/80 transition-colors group cursor-pointer"
                    >
                      <td className="py-3 px-3 font-mono font-medium text-slate-900 truncate max-w-[180px]">
                        {rev.repoFullName || rev.repo || "repo"}
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-600">
                        #{rev.prNumber || rev.pr_number || rev.id}
                      </td>
                      <td className="py-3 px-3 text-slate-900 font-medium truncate max-w-xs">
                        {rev.title || rev.summary || "Pull Request Review"}
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border ${v.badge}`}
                        >
                          <span>{v.icon}</span>
                          <span>{v.label}</span>
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-500 text-[11px] whitespace-nowrap">
                        {dateStr}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Link
                          href={`/reviews/${prTargetId}`}
                          className="inline-flex items-center gap-1 text-slate-900 hover:text-slate-600 font-semibold text-xs transition-colors"
                        >
                          View <span>→</span>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AuthGuard>
      <DashboardLayout>
        <DashboardContent />
      </DashboardLayout>
    </AuthGuard>
  );
}
