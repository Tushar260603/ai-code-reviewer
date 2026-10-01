'use strict';

/**
 * services/githubClient.js
 *
 * GitHub API helpers used by the review worker:
 *
 *  - getPRDiff(repoFullName, prNumber, token)
 *      Fetches the unified diff for a pull request.
 *
 *  - postReviewComment(repoFullName, prNumber, reviewResult, token)
 *      Posts a formatted markdown summary comment to the PR.
 *
 * Uses the GitHub REST API v3 directly via Axios so there is no Octokit
 * dependency required (plain HTTP is simpler and keeps the dep tree small).
 */

const axios = require('axios');

// ── Helpers ────────────────────────────────────────────────────────────────────

/**
 * Build an Axios instance pre-configured for the GitHub REST API.
 *
 * @param {string} token - GitHub personal access token or installation token
 * @returns {import('axios').AxiosInstance}
 */
function githubHttp(token) {
  return axios.create({
    baseURL: 'https://api.github.com',
    timeout: 30_000,
    headers: {
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
}

// ── getPRDiff ──────────────────────────────────────────────────────────────────

/**
 * Fetch the unified diff for a pull request.
 *
 * @param {string} repoFullName  - "owner/repo"
 * @param {number|string} prNumber
 * @param {string} [token]       - GitHub token (optional for public repos)
 * @returns {Promise<string>}    - Raw unified diff string
 */
async function getPRDiff(repoFullName, prNumber, token) {
  const http = githubHttp(token);

  try {
    const { data } = await http.get(`/repos/${repoFullName}/pulls/${prNumber}`, {
      headers: { Accept: 'application/vnd.github.diff' },
    });
    return data; // GitHub returns raw diff text when Accept: ...diff is set
  } catch (err) {
    const status = err.response?.status;
    const msg    = err.response?.data?.message ?? err.message;
    throw new Error(`Failed to fetch PR diff for ${repoFullName}#${prNumber} (${status}): ${msg}`);
  }
}

// ── getChangedFiles ────────────────────────────────────────────────────────────

/**
 * Return the list of changed file paths in a PR.
 *
 * @param {string} repoFullName
 * @param {number|string} prNumber
 * @param {string} [token]
 * @returns {Promise<string[]>}
 */
async function getChangedFiles(repoFullName, prNumber, token) {
  const http = githubHttp(token);

  const files = [];
  let page = 1;

  // GitHub paginates at 30 files per page by default; request 100
  while (true) {
    const { data } = await http.get(
      `/repos/${repoFullName}/pulls/${prNumber}/files`,
      { params: { per_page: 100, page } }
    );
    if (!data.length) break;
    files.push(...data.map((f) => f.filename));
    if (data.length < 100) break;
    page++;
  }

  return files;
}

// ── postReviewComment ──────────────────────────────────────────────────────────

/**
 * Post a formatted markdown summary comment to a PR.
 *
 * @param {string} repoFullName
 * @param {number|string} prNumber
 * @param {object} reviewResult   - FastAPI ReviewResponse JSON
 * @param {string} [token]
 * @returns {Promise<object>}     - GitHub API response for the created comment
 */
async function postReviewComment(repoFullName, prNumber, reviewResult, token) {
  const http = githubHttp(token);

  const body = buildCommentBody(reviewResult);

  try {
    const { data } = await http.post(
      `/repos/${repoFullName}/issues/${prNumber}/comments`,
      { body }
    );
    return data;
  } catch (err) {
    const status = err.response?.status;
    const msg    = err.response?.data?.message ?? err.message;
    throw new Error(
      `Failed to post review comment on ${repoFullName}#${prNumber} (${status}): ${msg}`
    );
  }
}

// ── Comment body builder ───────────────────────────────────────────────────────

const VERDICT_EMOJI = {
  approve:         '✅',
  request_changes: '❌',
  comment:         '💬',
};

const SEVERITY_EMOJI = {
  critical: '🔴',
  high:     '🟠',
  medium:   '🟡',
  low:      '🔵',
  info:     '⚪',
};

/**
 * Build a markdown comment body from a FastAPI ReviewResponse.
 *
 * @param {object} result
 * @returns {string}
 */
function buildCommentBody(result) {
  const verdict  = result.verdict ?? 'comment';
  const emoji    = VERDICT_EMOJI[verdict] ?? '💬';
  const summary  = result.summary ?? 'No summary provided.';
  const findings = result.findings ?? [];

  const lines = [
    `## ${emoji} AI Code Review — \`${verdict.replace('_', ' ').toUpperCase()}\``,
    '',
    summary,
    '',
  ];

  // Agent breakdown table
  if (result.agent_breakdown && Object.keys(result.agent_breakdown).length) {
    lines.push('### Agent Breakdown');
    lines.push('');
    lines.push('| Agent | Findings |');
    lines.push('|-------|----------|');
    for (const [agent, count] of Object.entries(result.agent_breakdown)) {
      lines.push(`| ${agent} | ${count} |`);
    }
    lines.push('');
  }

  // Findings list
  if (findings.length) {
    lines.push(`### Findings (${findings.length})`);
    lines.push('');

    for (const f of findings) {
      const sev  = f.severity ?? 'info';
      const sevE = SEVERITY_EMOJI[sev] ?? '⚪';
      const loc  = f.file ? (f.line ? `\`${f.file}:${f.line}\`` : `\`${f.file}\``) : '';
      lines.push(`- ${sevE} **[${sev.toUpperCase()}]** ${loc ? `${loc} — ` : ''}${f.message}`);
      if (f.suggestion) {
        lines.push(`  > 💡 ${f.suggestion}`);
      }
    }
    lines.push('');
  } else {
    lines.push('_No issues found._');
    lines.push('');
  }

  lines.push('---');
  lines.push('*Generated by AI Code Reviewer*');

  return lines.join('\n');
}

// ── Repository & Webhook Management ──────────────────────────────────────────

/**
 * List all repositories accessible to the authenticated user.
 *
 * @param {string} token - User's GitHub access token
 * @returns {Promise<Array<object>>}
 */
async function listUserRepos(token) {
  if (!token) throw new Error('GitHub access token is required to list repositories.');
  const http = githubHttp(token);

  const repos = [];
  let page = 1;

  while (true) {
    const { data } = await http.get('/user/repos', {
      params: {
        per_page: 100,
        page,
        sort: 'updated',
        direction: 'desc',
        affiliation: 'owner,collaborator,organization_member',
      },
    });

    if (!data.length) break;

    for (const r of data) {
      // Only include repos where user has admin or push permission
      if (r.permissions?.admin || r.permissions?.push) {
        repos.push({
          id: r.id,
          fullName: r.full_name,
          name: r.name,
          owner: r.owner?.login,
          private: r.private,
          htmlUrl: r.html_url,
          defaultBranch: r.default_branch,
          updatedAt: r.updated_at,
          permissions: r.permissions,
        });
      }
    }

    if (data.length < 100) break;
    page++;
  }

  return repos;
}

/**
 * Automatically create a webhook on a GitHub repository.
 * If a webhook with the same target URL already exists, returns the existing one.
 *
 * @param {string} repoFullName - "owner/repo"
 * @param {string} webhookUrl - Public URL where GitHub sends webhooks
 * @param {string} secret - Shared webhook secret
 * @param {string} token - User's GitHub access token
 * @returns {Promise<object>}
 */
async function createRepoWebhook(repoFullName, webhookUrl, secret, token) {
  if (!token) throw new Error('GitHub access token is required to create a webhook.');
  const http = githubHttp(token);

  try {
    // 1. Check if hook already exists
    const { data: existingHooks } = await http.get(`/repos/${repoFullName}/hooks`);
    const normalizedTarget = webhookUrl.replace(/\/+$/, '');

    const found = existingHooks.find(
      (h) => h.config?.url && h.config.url.replace(/\/+$/, '') === normalizedTarget
    );

    if (found) {
      return { hook: found, alreadyExists: true };
    }

    // 2. Create the webhook
    const { data: newHook } = await http.post(`/repos/${repoFullName}/hooks`, {
      name: 'web',
      active: true,
      events: ['pull_request', 'issue_comment'],
      config: {
        url: webhookUrl,
        content_type: 'json',
        secret: secret || undefined,
        insecure_ssl: '0',
      },
    });

    return { hook: newHook, alreadyExists: false };
  } catch (err) {
    const status = err.response?.status;
    const msg = err.response?.data?.message || err.message;
    throw new Error(`Failed to configure webhook on ${repoFullName} (${status}): ${msg}`);
  }
}

/**
 * Remove an automated webhook from a GitHub repository.
 *
 * @param {string} repoFullName - "owner/repo"
 * @param {string} webhookUrl - Public URL of the webhook to delete
 * @param {string} token - User's GitHub access token
 * @returns {Promise<boolean>}
 */
async function deleteRepoWebhook(repoFullName, webhookUrl, token) {
  if (!token) throw new Error('GitHub access token is required to delete a webhook.');
  const http = githubHttp(token);

  try {
    const { data: existingHooks } = await http.get(`/repos/${repoFullName}/hooks`);
    const normalizedTarget = webhookUrl.replace(/\/+$/, '');

    const found = existingHooks.find(
      (h) => h.config?.url && h.config.url.replace(/\/+$/, '') === normalizedTarget
    );

    if (found) {
      await http.delete(`/repos/${repoFullName}/hooks/${found.id}`);
      return true;
    }
    return false;
  } catch (err) {
    const status = err.response?.status;
    const msg = err.response?.data?.message || err.message;
    throw new Error(`Failed to remove webhook from ${repoFullName} (${status}): ${msg}`);
  }
}

module.exports = {
  getPRDiff,
  getChangedFiles,
  postReviewComment,
  buildCommentBody, // exported for testing
  listUserRepos,
  createRepoWebhook,
  deleteRepoWebhook,
};

