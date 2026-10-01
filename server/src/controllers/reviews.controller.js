"use strict";

/**
 * controllers/reviews.controller.js
 *
 * Handlers for review retrieval endpoints:
 *   - GET /api/reviews
 *   - GET /api/reviews/:id
 */

const { Review, PullRequest, Finding } = require("../models");
const { GITHUB_TOKEN } = require("../config/env");

/**
 * GET /api/reviews
 * Return recent pull request reviews with repository metadata.
 */
async function getRecentReviews(req, res) {
  try {
    const reviews = await Review.findAll({
      include: [
        {
          model: PullRequest,
          as: "pullRequest",
          attributes: [
            "id",
            "repoFullName",
            "prNumber",
            "title",
            "author",
            "status",
            "lastReviewedSha",
          ],
        },
      ],
      order: [["createdAt", "DESC"]],
      limit: 50,
    });

    const formatted = reviews.map((r) => ({
      id: r.id,
      prId: r.prId,
      repoFullName: r.pullRequest?.repoFullName || "unknown",
      prNumber: r.pullRequest?.prNumber || r.prId,
      title: r.pullRequest?.title || `Pull Request #${r.pullRequest?.prNumber || r.prId}`,
      author: r.pullRequest?.author || null,
      status: r.pullRequest?.status || "completed",
      lastReviewedSha: r.triggeredBySha,
      verdict: r.verdict,
      summary: r.summary,
      createdAt: r.createdAt,
    }));

    return res.status(200).json(formatted);
  } catch (err) {
    console.error("[Reviews Controller] Error fetching recent reviews:", err.message);
    return res.status(500).json({
      error: "Internal Server Error",
      message: "Failed to fetch reviews",
    });
  }
}

/**
 * GET /api/reviews/:id
 * Return review details and associated specialist findings by Review ID or PR ID.
 */
async function getReviewDetails(req, res) {
  const { id } = req.params;

  try {
    // 1. First check if id matches a PullRequest ID -> return its latest review
    let review = await Review.findOne({
      where: { prId: id },
      include: [
        { model: PullRequest, as: "pullRequest" },
        { model: Finding, as: "findings" },
      ],
      order: [["createdAt", "DESC"]],
    });

    // 2. If not found by prId, try finding by Review primary key
    if (!review) {
      review = await Review.findOne({
        where: { id },
        include: [
          { model: PullRequest, as: "pullRequest" },
          { model: Finding, as: "findings" },
        ],
      });
    }

    if (!review) {
      return res.status(404).json({
        error: "Not Found",
        message: `Review with identifier ${id} not found`,
      });
    }

    const response = {
      id: review.id,
      prId: review.prId,
      repoFullName: review.pullRequest?.repoFullName || "unknown",
      prNumber: review.pullRequest?.prNumber || review.prId,
      title: review.pullRequest?.title || `Pull Request #${review.pullRequest?.prNumber || review.prId}`,
      author: review.pullRequest?.author || null,
      status: review.pullRequest?.status || "completed",
      triggeredBySha: review.triggeredBySha,
      verdict: review.verdict,
      summary: review.summary,
      createdAt: review.createdAt,
      findings: review.findings || [],
    };

    return res.status(200).json(response);
  } catch (err) {
    console.error(`[Reviews Controller] Error fetching review ${id}:`, err.message);
    return res.status(500).json({
      error: "Internal Server Error",
      message: "Failed to fetch review details",
    });
  }
}

/**
 * POST /api/reviews/trigger
 * Trigger an instant review for any PR on demand.
 */
async function triggerManualReview(req, res) {
  const { repoFullName, prNumber } = req.body;
  if (!repoFullName || !prNumber) {
    return res.status(400).json({
      error: "Bad Request",
      message: "Both repoFullName and prNumber are required.",
    });
  }

  // ── Respond IMMEDIATELY — no external calls before this line ────────────
  // GitHub fetch + AI review (~60-90s) all run in the background.
  res.status(202).json({
    success: true,
    message: `Review started for ${repoFullName}#${prNumber}. Results will appear in the dashboard shortly.`,
    status: "processing",
  });

  // ── Everything below runs AFTER the response is sent ────────────────────
  (async () => {
    try {
      const { User } = require("../models");
      const user = req.user?.id ? await User.findByPk(req.user.id) : null;
      const token = user?.accessToken || GITHUB_TOKEN;

      console.log(`[Trigger] Fetching PR data for ${repoFullName}#${prNumber}, token=${token ? "present" : "MISSING"}`);

      const axios = require("axios");
      const ghRes = await axios.get(
        `https://api.github.com/repos/${repoFullName}/pulls/${prNumber}`,
        {
          timeout: 15000,
          headers: {
            Accept: "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        }
      );

      const prData = ghRes.data;
      const jobData = {
        repoFullName,
        repoUrl: prData.head?.repo?.html_url || `https://github.com/${repoFullName}`,
        prNumber: Number(prNumber),
        title: prData.title,
        author: prData.user?.login,
        baseSha: prData.base?.sha,
        headSha: prData.head?.sha,
        action: "manual_trigger",
        githubToken: token,
      };

      const { processReviewJob } = require("../queue/reviewWorker");
      await processReviewJob({
        id: `manual-${Date.now()}`,
        data: jobData,
        updateProgress: async () => {},
      });

      console.log(`[Trigger] Review complete for ${repoFullName}#${prNumber}`);
    } catch (err) {
      const detail = err.response?.data?.message || err.message;
      console.error(`[Trigger] Background review failed for ${repoFullName}#${prNumber}:`, detail);
    }
  })();
}

/**
 * GET /api/reviews/:id/diff
 * Fetch unified diff and changed files for a review.
 */
async function getReviewDiff(req, res) {
  const { id } = req.params;
  try {
    let review = await Review.findOne({
      where: { id },
      include: [{ model: PullRequest, as: "pullRequest" }],
    });
    if (!review) {
      review = await Review.findOne({
        where: { prId: id },
        include: [{ model: PullRequest, as: "pullRequest" }],
        order: [["createdAt", "DESC"]],
      });
    }
    if (!review || !review.pullRequest) {
      return res.status(404).json({ error: "Review or PR not found" });
    }

    const { User } = require("../models");
    const user = await User.findByPk(req.user?.id);
    const token = user?.accessToken || process.env.GITHUB_TOKEN;
    const { getPRDiff, getChangedFiles } = require("../services/githubClient");

    const [diff, files] = await Promise.all([
      getPRDiff(review.pullRequest.repoFullName, review.pullRequest.prNumber, token).catch(() => ""),
      getChangedFiles(review.pullRequest.repoFullName, review.pullRequest.prNumber, token).catch(() => []),
    ]);

    return res.status(200).json({ diff, files });
  } catch (err) {
    console.error(`[Reviews Controller] Error fetching diff for review ${id}:`, err.message);
    return res.status(500).json({
      error: "Failed to fetch PR diff",
      message: err.message,
    });
  }
}

module.exports = {
  getRecentReviews,
  getReviewDetails,
  triggerManualReview,
  getReviewDiff,
};


