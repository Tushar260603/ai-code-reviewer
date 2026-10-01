"use client";

import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const COLORS = {
  security: "#ef4444", // red-500
  style: "#6366f1",    // indigo-500
  logic: "#f59e0b",    // amber-500
};

/**
 * AgentBreakdownChart renders a clean bar chart showing finding distribution
 * across security, style, and logic specialist agents.
 *
 * @param {object} props
 * @param {number} [props.security=0]
 * @param {number} [props.style=0]
 * @param {number} [props.logic=0]
 */
export default function AgentBreakdownChart({
  security = 0,
  style = 0,
  logic = 0,
}) {
  const data = [
    { name: "Security", key: "security", count: Number(security || 0) },
    { name: "Style", key: "style", count: Number(style || 0) },
    { name: "Logic", key: "logic", count: Number(logic || 0) },
  ];

  const total = data.reduce((acc, curr) => acc + curr.count, 0);

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Agent Breakdown</h3>
          <p className="text-xs text-slate-500">Distribution of findings by specialist</p>
        </div>
        <span className="text-xs font-medium text-slate-600 bg-slate-100 px-2 py-1 rounded">
          {total} Total {total === 1 ? "Issue" : "Issues"}
        </span>
      </div>

      <div className="h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 8, right: 10, left: -20, bottom: 0 }}
          >
            <XAxis
              dataKey="name"
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={{ stroke: "#e2e8f0" }}
            />
            <YAxis
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip
              cursor={{ fill: "#f8fafc" }}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const item = payload[0].payload;
                  return (
                    <div className="bg-slate-900 text-white text-xs px-2.5 py-1.5 rounded shadow">
                      <p className="font-semibold">{item.name}</p>
                      <p className="text-slate-300">
                        {item.count} {item.count === 1 ? "finding" : "findings"}
                      </p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {data.map((entry) => (
                <Cell key={entry.key} fill={COLORS[entry.key] || "#94a3b8"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
