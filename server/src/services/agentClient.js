'use strict';

/**
 * services/agentClient.js
 *
 * Thin Axios wrapper around the FastAPI /review endpoint.
 *
 * The FastAPI service (agent-service/) accepts:
 *   POST /review
 *   {
 *     repo_url:      string,
 *     pr_number:     number,
 *     diff:          string,
 *     changed_files: string[],
 *     base_sha:      string,
 *     head_sha:      string,
 *   }
 *
 * It returns a ReviewResponse matching agent-service/app/models/review_result.py.
 */

const axios = require('axios');
const { FASTAPI_URL } = require('../config/env');

// ── Axios instance ─────────────────────────────────────────────────────────────

const agentHttp = axios.create({
  baseURL: FASTAPI_URL,
  timeout: 5 * 60 * 1000, // 5 minutes — LLM calls can be slow
  headers: { 'Content-Type': 'application/json' },
});

// ── Public API ─────────────────────────────────────────────────────────────────

/**
 * callAgentService(payload)
 *
 * Posts a review request to the FastAPI agent service and returns the
 * structured ReviewResponse.
 *
 * @param {object} payload
 * @param {string} payload.repo_url       - Full GitHub repo URL
 * @param {number} payload.pr_number      - Pull request number
 * @param {string} payload.diff           - Unified diff string
 * @param {string[]} [payload.changed_files] - List of changed file paths
 * @param {string} [payload.base_sha]     - Base commit SHA
 * @param {string} [payload.head_sha]     - Head commit SHA
 *
 * @returns {Promise<object>} FastAPI ReviewResponse JSON
 * @throws  {Error}           On non-2xx response or network failure
 */
async function callAgentService(payload) {
  const body = {
    repo_url:      payload.repo_url      ?? payload.repoUrl      ?? '',
    pr_number:     Number(payload.pr_number ?? payload.prNumber ?? 0),
    diff:          payload.diff          ?? '',
    changed_files: payload.changed_files ?? payload.changedFiles ?? [],
    base_sha:      payload.base_sha      ?? payload.baseSha      ?? '',
    head_sha:      payload.head_sha      ?? payload.headSha      ?? '',
  };

  try {
    const { data } = await agentHttp.post('/review', body);
    return data;
  } catch (err) {
    // Axios wraps HTTP error responses — surface the FastAPI detail if available
    if (err.response) {
      const detail = err.response.data?.detail ?? JSON.stringify(err.response.data);
      const error = new Error(
        `Agent service returned ${err.response.status}: ${detail}`
      );
      error.status = err.response.status;
      error.data   = err.response.data;
      throw error;
    }
    // Network / timeout errors
    throw new Error(`Agent service unreachable: ${err.message}`);
  }
}

module.exports = { callAgentService };
