"use strict";

/**
 * queue/reviewWorker.js
 *
 * BullMQ Worker — processes async review jobs enqueued by the webhook controller.
 * In local dev without Redis, reviews are executed directly via processReviewJob.
 */

const { Worker, UnrecoverableError } = require("bullmq");
const IORedis = require("ioredis");

const { REDIS_URL, GITHUB_TOKEN } = require("../config/env");
const { PullRequest, Review, Finding } = require("../models");
const { callAgentService } = require("../services/agentClient");
const {
  getPRDiff,
  getChangedFiles,
  postReviewComment,
} = require("../services/githubClient");

const QUEUE_NAME = "review-queue";

/**
 * Resolve the GitHub token for API calls.
 */
function resolveToken(jobData) {
  return (
    jobData.installationToken ?? jobData.githubToken ?? GITHUB_TOKEN ?? undefined
  );
}

/**
 * Map a FastAPI severity string to the Finding ENUM values.
 */
function normalizeSeverity(severity) {
  const allowed = ["critical", "high", "medium", "low"];
  return allowed.includes(severity) ? severity : "low";
}

/**
 * Map a FastAPI category string to the agentType ENUM values.
 */
function normalizeAgentType(category) {
  const allowed = ["security", "style", "logic"];
  const lower = String(category ?? "").toLowerCase();
  return allowed.includes(lower) ? lower : "logic";
}

// ── Main processor ─────────────────────────────────────────────────────────────

/**
 * @param {object} job - Job instance or mock job object
 */
async function processReviewJob(job) {
  const {
    repoFullName,
    repoUrl,
    prNumber,
    title,
    author,
    baseSha,
    headSha,
    action,
  } = job.data;

  const token = resolveToken(job.data);

  console.log(
    `[Worker] Processing PR Review: ${repoFullName}#${prNumber} @ ${headSha?.slice(0, 7)} (${action})`
  );

  // ── 1. Find-or-create PullRequest ─────────────────────────────────────────
  const [pr] = await PullRequest.findOrCreate({
    where: { repoFullName, prNumber },
    defaults: {
      repoFullName,
      prNumber,
      title:          title  ?? `PR #${prNumber}`,
      author:         author ?? null,
      status:         "reviewing",
      lastReviewedSha: headSha,
    },
  });

  // If already exists, mark as reviewing
  if (pr.status !== "reviewing") {
    await pr.update({ status: "reviewing" });
  }

  // ── 2. Idempotency guard ─────────────────────────────────────────────────
  if (headSha && action !== "manual_trigger") {
    const existingReview = await Review.findOne({
      where: { prId: pr.id, triggeredBySha: headSha },
    });

    if (existingReview) {
      console.log(
        `[Worker] Review already exists for ${repoFullName}#${prNumber}@${headSha.slice(0, 7)}, skipping.`
      );
      return existingReview;
    }
  } else if (headSha && action === "manual_trigger") {
    // Clean old review for this SHA to re-run fresh analysis
    await Review.destroy({
      where: { prId: pr.id, triggeredBySha: headSha },
    });
  }

  // ── 3. Fetch diff ────────────────────────────────────────────────────────
  if (job.updateProgress) await job.updateProgress(10);
  console.log(`[Worker] Fetching unified diff for ${repoFullName}#${prNumber}...`);
  const diff = await getPRDiff(repoFullName, prNumber, token);

  // ── 4. Fetch changed files ───────────────────────────────────────────────
  if (job.updateProgress) await job.updateProgress(20);
  const changedFiles = await getChangedFiles(repoFullName, prNumber, token);

  // ── 5. Call FastAPI agent service ────────────────────────────────────────
  if (job.updateProgress) await job.updateProgress(30);
  console.log(`[Worker] Calling Python AI Supervisor & Specialist Agents for ${repoFullName}#${prNumber}...`);
  const reviewResult = await callAgentService({
    repo_url:      repoUrl,
    pr_number:     prNumber,
    diff,
    changed_files: changedFiles,
    base_sha:      baseSha,
    head_sha:      headSha,
  });

  // ── 6. Create Review row ─────────────────────────────────────────────────
  if (job.updateProgress) await job.updateProgress(60);
  const review = await Review.create({
    prId:           pr.id,
    triggeredBySha: headSha || "manual",
    verdict:        reviewResult.verdict ?? "comment",
    summary:        reviewResult.summary ?? null,
  });

  // ── 7. Bulk-insert Findings ──────────────────────────────────────────────
  if (job.updateProgress) await job.updateProgress(70);
  const rawFindings = reviewResult.findings ?? [];

  if (rawFindings.length > 0) {
    await Finding.bulkCreate(
      rawFindings.map((f) => ({
        reviewId:  review.id,
        agentType: normalizeAgentType(f.category),
        file:      f.file     ?? "unknown",
        line:      f.line     ?? 1,
        severity:  normalizeSeverity(f.severity),
        message:   f.message  ?? "",
        resolved:  false,
      })),
      { validate: true }
    );
  }

  // ── 8. Update PullRequest ────────────────────────────────────────────────
  if (job.updateProgress) await job.updateProgress(85);
  await pr.update({
    status:          "completed",
    lastReviewedSha: headSha || pr.lastReviewedSha,
    title:           title  ?? pr.title,
    author:          author ?? pr.author,
  });

  // ── 9. Post GitHub comment (non-fatal) ───────────────────────────────────
  if (job.updateProgress) await job.updateProgress(92);
  try {
    console.log(`[Worker] Posting AI review summary comment to GitHub PR #${prNumber}...`);
    await postReviewComment(repoFullName, prNumber, reviewResult, token);
  } catch (commentErr) {
    console.warn(
      `[Worker] Could not post comment on ${repoFullName}#${prNumber}: ${commentErr.message}`
    );
  }

  if (job.updateProgress) await job.updateProgress(100);
  console.log(
    `[Worker] ✅ Review complete for PR #${prNumber} — Verdict: ${review.verdict.toUpperCase()}, Findings: ${rawFindings.length}`
  );

  return {
    reviewId:      review.id,
    prId:          pr.id,
    verdict:       review.verdict,
    findingsCount: rawFindings.length,
  };
}

// ── Optional BullMQ Worker instance (if Redis is online) ─────────────────────
let worker = null;
let redisConnection = null;

try {
  redisConnection = new IORedis(REDIS_URL, {
    maxRetriesPerRequest: null,
    enableReadyCheck: false,
    retryStrategy(times) {
      if (times > 2) return null; // Stop reconnect spam if Redis is offline
      return 1000;
    },
    lazyConnect: true,
  });

  redisConnection.on("error", () => {
    // Silently handle offline Redis in local dev
  });

  worker = new Worker(QUEUE_NAME, processReviewJob, {
    connection: redisConnection,
    concurrency: Number(process.env.WORKER_CONCURRENCY ?? 3),
  });

  worker.on("error", () => {
    // Silently handle worker disconnects
  });
} catch (_) {
  // Direct fallback used when Redis is unavailable
}

async function shutdownWorker() {
  if (worker) {
    try {
      await worker.close();
    } catch (_) {}
  }
  if (redisConnection) {
    try {
      await redisConnection.quit();
    } catch (_) {}
  }
}

process.on("SIGTERM", shutdownWorker);
process.on("SIGINT",  shutdownWorker);

module.exports = { worker, processReviewJob, shutdownWorker };
