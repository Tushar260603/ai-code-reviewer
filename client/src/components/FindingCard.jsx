import React from "react";
import SeverityBadge from "./SeverityBadge";

const AGENT_COLORS = {
  security: "bg-red-50 text-red-700 border-red-200",
  style: "bg-indigo-50 text-indigo-700 border-indigo-200",
  logic: "bg-amber-50 text-amber-700 border-amber-200",
};

/**
 * Render message with intelligent diff highlighting (+ green, - red) and code blocks.
 */
function FormattedFindingMessage({ message }) {
  if (!message) return null;

  // Split by code fences if any
  const parts = message.split(/(```[\s\S]*?```)/g);

  return (
    <div className="text-xs text-slate-800 space-y-2 leading-relaxed">
      {parts.map((part, index) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          const lines = part.slice(3, -3).replace(/^[a-z]+\n/, "").split("\n");
          return (
            <div
              key={index}
              className="bg-slate-900 text-slate-100 rounded-md p-3 font-mono text-[11px] overflow-x-auto my-2"
            >
              {lines.map((line, lIdx) => {
                const isAddition = line.startsWith("+");
                const isRemoval = line.startsWith("-");
                return (
                  <div
                    key={lIdx}
                    className={`py-0.5 px-1 rounded ${
                      isAddition
                        ? "bg-emerald-950/70 text-emerald-300 font-medium"
                        : isRemoval
                        ? "bg-red-950/70 text-red-300 line-through opacity-85"
                        : "text-slate-300"
                    }`}
                  >
                    {line}
                  </div>
                );
              })}
            </div>
          );
        }

        return (
          <p key={index} className="whitespace-pre-wrap">
            {part}
          </p>
        );
      })}
    </div>
  );
}

/**
 * FindingCard component for displaying an individual agent review finding.
 */
export default function FindingCard({
  file,
  line,
  severity = "low",
  message,
  suggestion,
  agentType = "logic",
  resolved = false,
}) {
  const normAgent = String(agentType || "logic").toLowerCase();
  const agentBadgeClass = AGENT_COLORS[normAgent] || "bg-slate-100 text-slate-700 border-slate-200";

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 transition-colors hover:border-slate-300 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <SeverityBadge severity={severity} />
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border capitalize ${agentBadgeClass}`}
          >
            {normAgent}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          {resolved ? (
            <span className="inline-flex items-center gap-1 text-emerald-600 font-medium text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              Resolved
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-slate-500 font-medium text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full border border-slate-400"></span>
              Open
            </span>
          )}
        </div>
      </div>

      {/* Main Message */}
      <FormattedFindingMessage message={message} />

      {/* Code Suggestion / Fix Diff if provided */}
      {suggestion && (
        <div className="mt-2.5 bg-slate-50 border border-slate-200 rounded-md p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-700 mb-1.5">
            <span>💡</span>
            <span>Suggested Change</span>
          </div>
          <FormattedFindingMessage message={suggestion} />
        </div>
      )}

      {/* File & Line Tag */}
      {file && (
        <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-600 bg-slate-50 border border-slate-200 rounded px-2 py-1 w-fit">
          <svg
            className="w-3.5 h-3.5 text-slate-400 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <span className="truncate">{file}</span>
          {line !== undefined && line !== null && (
            <span className="text-slate-400 font-semibold">:{line}</span>
          )}
        </div>
      )}
    </div>
  );
}
