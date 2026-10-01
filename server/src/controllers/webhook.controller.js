/**
 * webhook.controller.js
 * Controller handling GitHub webhook deliveries.
 */

const reviewQueue = require("../queues/review.queue");

/**
 * Handle incoming GitHub webhooks.
 * Verifies event type, filters actions, extracts PR metadata, enqueues the review job,
 * and responds immediately with HTTP 200.
 */
async function handleGitHubWebhook(req, res) {
  const event = req.headers["x-github-event"];
  const deliveryId = req.headers["x-github-delivery"];
  const payload = req.body;

  // ── Step 1: Event type filtering ──────────────────────────────────────────
  if (event !== "pull_request") {
    console.log(`[Webhook] Ignored event type: '${event}' (delivery: ${deliveryId})`);
    return res.status(200).json({
      status: "ignored",
      reason: `Event '${event}' is not supported. Only 'pull_request' events are processed.`,
    });
  }

  // ── Step 2: Validate payload structure ───────────────────────────────────
  if (!payload || !payload.pull_request || !payload.repository) {
    console.warn(`[Webhook] Malformed pull_request payload (delivery: ${deliveryId})`);
    return res.status(400).json({
      error: "Malformed pull_request payload",
    });
  }

  const { action, pull_request: pr, repository: repo, sender } = payload;

  // ── Step 3: Action filtering (process only 'opened' and 'synchronize') ────
  const ALLOWED_ACTIONS = ["opened", "synchronize"];
  if (!ALLOWED_ACTIONS.includes(action)) {
    console.log(
      `[Webhook] Ignored PR action: '${action}' for PR #${pr.number} in ${repo.full_name}`
    );
    return res.status(200).json({
      status: "ignored",
      reason: `Action '${action}' is ignored. Only 'opened' and 'synchronize' actions are reviewed.`,
    });
  }

  // ── Step 4: Extract PR metadata ──────────────────────────────────────────
  const jobData = {
    deliveryId,
    repoUrl: repo.clone_url || repo.html_url,
    repoFullName: repo.full_name,
    prNumber: pr.number,
    prUrl: pr.html_url,
    diffUrl: pr.diff_url,
    baseSha: pr.base ? pr.base.sha : null,
    headSha: pr.head ? pr.head.sha : null,
    action,
    sender: sender ? sender.login : undefined,
  };

  // ── Step 5: Queue dispatch (with direct fallback if Redis is offline) ────
  try {
    const job = await reviewQueue.addReviewJob(jobData, deliveryId);
    return res.status(200).json({
      status: "queued",
      pr_number: pr.number,
      delivery_id: deliveryId,
      job_id: job.id,
    });
  } catch (error) {
    console.warn(
      `[Webhook] Queue unavailable (${error.message}). Processing review directly in background for PR #${pr.number}...`
    );

    // Run review directly without failing the webhook
    const { processReviewJob } = require("../queue/reviewWorker");
    processReviewJob({
      id: deliveryId || `sync-${Date.now()}`,
      data: jobData,
      updateProgress: async () => {},
    }).catch((err) => {
      console.error(`[Webhook] Direct review processing failed for PR #${pr.number}:`, err.message);
    });

    return res.status(200).json({
      status: "processing_direct",
      pr_number: pr.number,
      delivery_id: deliveryId,
    });
  }
}

module.exports = {
  handleGitHubWebhook,
};
