/**
 * lib/mockMetrics.js
 *
 * Clearly marked mock metrics data used as fallback when GET /api/metrics
 * is not yet available from the backend.
 *
 * Interface expectation matches specification:
 *   - findingsOverTime: [{ date, security, style, logic }]
 *   - evaluationRuns: [{ date, precision, recall }]
 */

export const mockMetricsData = {
  isMock: true,
  summary: {
    totalFindings: 42,
    avgPrecision: 0.87,
    avgRecall: 0.82,
    activeRuns: 14,
  },
  findingsOverTime: [
    { date: "2026-09-20", security: 4, style: 2, logic: 3 },
    { date: "2026-09-21", security: 3, style: 1, logic: 2 },
    { date: "2026-09-22", security: 5, style: 3, logic: 1 },
    { date: "2026-09-23", security: 2, style: 4, logic: 2 },
    { date: "2026-09-24", security: 6, style: 2, logic: 4 },
    { date: "2026-09-25", security: 3, style: 3, logic: 1 },
    { date: "2026-09-26", security: 4, style: 1, logic: 2 },
    { date: "2026-09-27", security: 2, style: 2, logic: 1 },
  ],
  evaluationRuns: [
    { date: "2026-09-20", precision: 0.84, recall: 0.78 },
    { date: "2026-09-22", precision: 0.86, recall: 0.80 },
    { date: "2026-09-24", precision: 0.88, recall: 0.81 },
    { date: "2026-09-26", precision: 0.87, recall: 0.82 },
    { date: "2026-09-27", precision: 0.89, recall: 0.83 },
  ],
};
