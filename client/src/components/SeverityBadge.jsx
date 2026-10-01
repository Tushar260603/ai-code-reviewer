import React from "react";

const SEVERITY_STYLES = {
  critical: "bg-red-50 text-red-700 border-red-200 ring-red-500/10",
  high: "bg-orange-50 text-orange-700 border-orange-200 ring-orange-500/10",
  medium: "bg-amber-50 text-amber-700 border-amber-200 ring-amber-500/10",
  low: "bg-blue-50 text-blue-700 border-blue-200 ring-blue-500/10",
};

/**
 * SeverityBadge component for displaying finding severity with clean, accessible colors.
 * Supported: critical | high | medium | low
 */
export default function SeverityBadge({ severity = "low", className = "" }) {
  const norm = String(severity || "low").toLowerCase();
  const style = SEVERITY_STYLES[norm] || SEVERITY_STYLES.low;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider border ring-1 ring-inset ${style} ${className}`}
    >
      {norm}
    </span>
  );
}
