"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import AuthGuard from "../../../components/AuthGuard";
import DashboardLayout from "../../../components/DashboardLayout";
import FindingCard from "../../../components/FindingCard";
import AgentBreakdownChart from "../../../components/AgentBreakdownChart";
import { getReview, getReviewDiff } from "../../../lib/api";

function formatVerdict(verdict) {
  const norm = String(verdict || "").toLowerCase();
  switch (norm) {
    case "approve":
    case "approved":
      return {
        label: "Approved",
        badge: "bg-emerald-50 text-emerald-800 border-emerald-300",
        icon: "✓",
        description: "The multi-agent reviewer approved these changes.",
      };
    case "request_changes":
      return {
        label: "Changes Requested",
        badge: "bg-red-50 text-red-800 border-red-300",
        icon: "✕",
        description: "The multi-agent reviewer identified issues that should be addressed.",
      };
    case "comment":
    default:
      return {
        label: "Commented",
        badge: "bg-slate-100 text-slate-800 border-slate-300",
        icon: "💬",
        description: "Review comments and observations recorded.",
      };
  }
}

/**
 * Enhanced Diff Viewer Component with line numbers and color highlighting.
 */
function DiffViewer({ diffText, changedFiles }) {
  if (!diffText) {
    return (
      <div className="bg-white border border-dashed border-slate-200 rounded-lg p-8 text-center">
        <p className="text-xs text-slate-500">No diff contents available for this pull request.</p>
      </div>
    );
  }

  const lines = diffText.split("\n");
  let additions = 0;
  let deletions = 0;

  lines.forEach((l) => {
    if (l.startsWith("+") && !l.startsWith("+++")) additions++;
    if (l.startsWith("-") && !l.startsWith("---")) deletions++;
  });

  return (
    <div className="space-y-4">
      {/* Diff Meta Bar */}
      <div className="bg-white border border-slate-200 rounded-lg p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-slate-800">
            {changedFiles.length || 1} {changedFiles.length === 1 ? "file changed" : "files changed"}
          </span>
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span className="text-emerald-600 font-semibold">+{additions} lines</span>
            <span className="text-red-600 font-semibold">-{deletions} lines</span>
          </div>
        </div>
        {changedFiles.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {changedFiles.map((f, idx) => (
              <span
                key={idx}
                className="font-mono text-[11px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200"
              >
                {f}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Code Diff Box */}
      <div className="bg-slate-950 text-slate-100 rounded-lg border border-slate-800 overflow-hidden font-mono text-xs">
        <div className="bg-slate-900 border-b border-slate-800 px-4 py-2 flex items-center justify-between text-slate-400 text-[11px]">
          <span>Unified Git Diff</span>
          <span>UTF-8</span>
        </div>
        <div className="p-3 overflow-x-auto max-h-[600px] overflow-y-auto space-y-0.5">
          {lines.map((line, idx) => {
            const isFileHeader = line.startsWith("diff --git") || line.startsWith("+++ ") || line.startsWith("--- ");
            const isHunkHeader = line.startsWith("@@");
            const isAddition = line.startsWith("+") && !line.startsWith("+++");
            const isDeletion = line.startsWith("-") && !line.startsWith("---");

            let lineClass = "text-slate-300";
            let bgClass = "hover:bg-slate-900/60";

            if (isFileHeader) {
              lineClass = "text-yellow-400 font-bold";
              bgClass = "bg-slate-900/90 py-1 px-1 border-t border-slate-800 mt-2 first:mt-0";
            } else if (isHunkHeader) {
              lineClass = "text-cyan-400 font-semibold";
              bgClass = "bg-cyan-950/40 py-0.5 px-1";
            } else if (isAddition) {
              lineClass = "text-emerald-300";
              bgClass = "bg-emerald-950/60";
            } else if (isDeletion) {
              lineClass = "text-red-300";
              bgClass = "bg-red-950/60 opacity-80";
            }

            return (
              <div key={idx} className={`flex items-start gap-3 px-2 py-0.5 rounded ${bgClass}`}>
                <span className="w-8 text-right text-slate-600 select-none text-[10px] shrink-0">
                  {idx + 1}
                </span>
                <span className={`whitespace-pre flex-1 ${lineClass}`}>{line || " "}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function ReviewDetailContent() {
  const params = useParams();
  const prId = params?.prId;

  const [review, setReview] = useState(null);
  const [diffData, setDiffData] = useState({ diff: "", files: [] });
  const [activeTab, setActiveTab] = useState("findings"); // "findings" | "diff" | "agents"
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDetail = async () => {
    if (!prId) return;
    try {
      setLoading(true);
      setError(null);
      const [reviewRes, diffRes] = await Promise.all([
        getReview(prId),
        getReviewDiff(prId).catch(() => ({ diff: "", files: [] })),
      ]);
      setReview(reviewRes);
      setDiffData(diffRes || { diff: "", files: [] });
    } catch (err) {
      console.error("Failed to load review:", err);
      setError("Unable to load review details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [prId]);

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-3">
        <div className="w-7 h-7 border-2 border-slate-300 border-t-slate-900 rounded-full animate-spin" />
        <p className="text-xs font-medium text-slate-500">Loading multi-agent review analysis...</p>
      </div>
    );
  }

  if (error || !review) {
    return (
      <div className="space-y-4">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 font-medium transition-colors"
        >
          <span>←</span> Back to Dashboard
        </Link>
        <div className="p-8 text-center border border-red-200 bg-red-50/50 rounded-lg">
          <p className="text-xs font-medium text-red-700">{error || "Review not found."}</p>
          <button
            onClick={fetchDetail}
            className="mt-3 text-xs bg-white text-slate-700 hover:text-slate-900 border border-slate-300 px-3 py-1.5 rounded font-medium shadow-sm"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  const findings = Array.isArray(review.findings) ? review.findings : [];
  const securityFindings = findings.filter(
    (f) => String(f.agentType || f.category || "").toLowerCase() === "security"
  );
  const styleFindings = findings.filter(
    (f) => String(f.agentType || f.category || "").toLowerCase() === "style"
  );
  const logicFindings = findings.filter(
    (f) => String(f.agentType || f.category || "").toLowerCase() === "logic"
  );

  const verdictMeta = formatVerdict(review.verdict);

  return (
    <div className="space-y-6">
      {/* Back button */}
      <div>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 font-medium transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Dashboard
        </Link>
      </div>

      {/* Main Header Info Card */}
      <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono text-slate-500 mb-1">
              <span className="font-semibold text-slate-800">{review.repoFullName || "Repository"}</span>
              <span>/</span>
              <span>PR #{review.prNumber || prId}</span>
            </div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              {review.title || `Pull Request #${review.prNumber || prId}`}
            </h1>
            <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-slate-400 mt-1.5">
              {review.author && (
                <span>
                  Author: <span className="text-slate-700 font-medium">@{review.author}</span>
                </span>
              )}
              {review.triggeredBySha && (
                <span>
                  Commit: <span className="text-slate-700">{review.triggeredBySha.substring(0, 7)}</span>
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {review.repoFullName && review.prNumber && (
              <a
                href={`https://github.com/${review.repoFullName}/pull/${review.prNumber}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-slate-900 hover:bg-slate-800 text-white transition-colors shadow-sm"
              >
                <span>View on GitHub</span>
                <span className="text-[10px]">↗</span>
              </a>
            )}
            <span
              className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold border ${verdictMeta.badge}`}
            >
              <span>{verdictMeta.icon}</span>
              <span>{verdictMeta.label}</span>
            </span>
          </div>
        </div>

        {/* AI Supervisor Executive Summary */}
        <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            <span>AI Supervisor Executive Summary</span>
          </div>
          <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">
            {review.summary || "All automated specialist checks completed. No critical code quality violations found."}
          </p>
        </div>

        {/* Multi-Agent Quality Scorecards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
          <div className="p-3 rounded-lg border border-red-100 bg-red-50/40 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-bold text-red-900 uppercase">Security Agent</p>
              <p className="text-xs text-slate-600 mt-0.5">
                {securityFindings.length === 0 ? "No vulnerabilities found" : `${securityFindings.length} issue(s) flagged`}
              </p>
            </div>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${securityFindings.length === 0 ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
              {securityFindings.length === 0 ? "Passed ✓" : "Action Required"}
            </span>
          </div>

          <div className="p-3 rounded-lg border border-amber-100 bg-amber-50/40 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-bold text-amber-900 uppercase">Logic & Safety</p>
              <p className="text-xs text-slate-600 mt-0.5">
                {logicFindings.length === 0 ? "Clean control flow" : `${logicFindings.length} logic issue(s)`}
              </p>
            </div>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${logicFindings.length === 0 ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
              {logicFindings.length === 0 ? "Passed ✓" : "Review Suggested"}
            </span>
          </div>

          <div className="p-3 rounded-lg border border-indigo-100 bg-indigo-50/40 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-bold text-indigo-900 uppercase">Style & Quality</p>
              <p className="text-xs text-slate-600 mt-0.5">
                {styleFindings.length === 0 ? "Follows conventions" : `${styleFindings.length} style note(s)`}
              </p>
            </div>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${styleFindings.length === 0 ? "bg-emerald-100 text-emerald-800" : "bg-indigo-100 text-indigo-800"}`}>
              {styleFindings.length === 0 ? "Passed ✓" : "Notes Available"}
            </span>
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex border-b border-slate-200 gap-6 text-xs font-semibold">
        <button
          onClick={() => setActiveTab("findings")}
          className={`pb-2.5 border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "findings"
              ? "border-slate-900 text-slate-900"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <span>Findings & Recommendations</span>
          <span className="bg-slate-100 text-slate-700 text-[10px] px-1.5 py-0.5 rounded-full">
            {findings.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("diff")}
          className={`pb-2.5 border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "diff"
              ? "border-slate-900 text-slate-900"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <span>Files Changed & Diff</span>
          <span className="bg-slate-100 text-slate-700 text-[10px] px-1.5 py-0.5 rounded-full">
            {diffData.files.length || (diffData.diff ? 1 : 0)}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("agents")}
          className={`pb-2.5 border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "agents"
              ? "border-slate-900 text-slate-900"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <span>Agent Breakdown</span>
        </button>
      </div>

      {/* Tab 1: Findings */}
      {activeTab === "findings" && (
        <div className="space-y-6">
          {findings.length === 0 ? (
            <div className="bg-white border border-dashed border-slate-200 rounded-lg p-10 text-center space-y-2">
              <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto text-lg font-bold">
                ✓
              </div>
              <h3 className="text-sm font-bold text-slate-800">Clean Code Review Passed</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                The Security, Logic, and Style agents evaluated this diff. No critical bugs, injection vulnerabilities, or style violations were detected.
              </p>
              <div className="pt-2">
                <button
                  onClick={() => setActiveTab("diff")}
                  className="text-xs text-blue-600 hover:text-blue-800 font-semibold underline"
                >
                  Inspect code changes in Diff tab →
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Security Findings */}
              {securityFindings.length > 0 && (
                <section className="space-y-3">
                  <div className="flex items-center gap-2 pb-1 border-b border-red-100">
                    <span className="w-2 h-2 rounded-full bg-red-500" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-red-900">
                      Security Findings ({securityFindings.length})
                    </h3>
                  </div>
                  <div className="space-y-3">
                    {securityFindings.map((f) => (
                      <FindingCard key={f.id || `${f.file}-${f.line}`} {...f} />
                    ))}
                  </div>
                </section>
              )}

              {/* Logic Findings */}
              {logicFindings.length > 0 && (
                <section className="space-y-3">
                  <div className="flex items-center gap-2 pb-1 border-b border-amber-100">
                    <span className="w-2 h-2 rounded-full bg-amber-500" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-amber-900">
                      Logic Findings ({logicFindings.length})
                    </h3>
                  </div>
                  <div className="space-y-3">
                    {logicFindings.map((f) => (
                      <FindingCard key={f.id || `${f.file}-${f.line}`} {...f} />
                    ))}
                  </div>
                </section>
              )}

              {/* Style Findings */}
              {styleFindings.length > 0 && (
                <section className="space-y-3">
                  <div className="flex items-center gap-2 pb-1 border-b border-indigo-100">
                    <span className="w-2 h-2 rounded-full bg-indigo-500" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-900">
                      Style Findings ({styleFindings.length})
                    </h3>
                  </div>
                  <div className="space-y-3">
                    {styleFindings.map((f) => (
                      <FindingCard key={f.id || `${f.file}-${f.line}`} {...f} />
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Code Diff Viewer */}
      {activeTab === "diff" && (
        <DiffViewer diffText={diffData.diff} changedFiles={diffData.files} />
      )}

      {/* Tab 3: Agent Breakdown */}
      {activeTab === "agents" && (
        <div className="space-y-6">
          <AgentBreakdownChart
            security={securityFindings.length}
            style={styleFindings.length}
            logic={logicFindings.length}
          />
        </div>
      )}
    </div>
  );
}

export default function ReviewDetailPageClient() {
  return (
    <AuthGuard>
      <DashboardLayout>
        <ReviewDetailContent />
      </DashboardLayout>
    </AuthGuard>
  );
}
