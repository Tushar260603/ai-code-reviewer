/**
 * review.queue.js
 * BullMQ review queue backed by Redis for asynchronous pull-request processing.
 */

const { Queue } = require("bullmq");
const Redis = require("ioredis");
const { REDIS_URL } = require("../config/env");

let redisConnection = null;
let reviewQueue = null;

/**
 * Get or initialize the shared IORedis connection for BullMQ.
 * BullMQ requires `maxRetriesPerRequest: null`.
 */
function getRedisConnection() {
  if (!redisConnection) {
    redisConnection = new Redis(REDIS_URL, {
      maxRetriesPerRequest: null,
      enableReadyCheck: false,
      retryStrategy(times) {
        if (times > 2) return null; // Stop reconnect spam if Redis is offline
        return 1000;
      },
      lazyConnect: true,
    });

    redisConnection.on("connect", () => {
      console.log("[Redis] Connected successfully to queue store.");
    });

    redisConnection.on("error", () => {
      // Silently handle offline Redis in local development
    });
  }
  return redisConnection;
}

/**
 * Get or initialize the BullMQ review queue instance.
 */
function getReviewQueue() {
  if (!reviewQueue) {
    const connection = getRedisConnection();
    reviewQueue = new Queue("review-queue", {
      connection,
      defaultJobOptions: {
        attempts: 3,
        backoff: {
          type: "exponential",
          delay: 2000,
        },
        removeOnComplete: {
          count: 1000,
        },
        removeOnFail: {
          count: 5000,
        },
      },
    });
  }
  return reviewQueue;
}

/**
 * Add a review job to the queue.
 * Uses the GitHub delivery ID as the BullMQ jobId to guarantee idempotency
 * and prevent duplicate processing if GitHub redelivers the webhook.
 *
 * @param {Object} jobData - PR metadata required for review.
 * @param {string} [deliveryId] - GitHub X-GitHub-Delivery identifier.
 * @returns {Promise<import("bullmq").Job>}
 */
async function addReviewJob(jobData, deliveryId) {
  const queue = getReviewQueue();
  const jobId = deliveryId ? `github-${deliveryId}` : undefined;

  const job = await queue.add("pr-review", jobData, {
    jobId,
  });

  console.log(
    `[Queue] Enqueued PR review job id=${job.id} for PR #${jobData.prNumber} (${jobData.repoFullName})`
  );
  return job;
}

/**
 * Gracefully close the queue and Redis connection.
 */
async function closeReviewQueue() {
  if (reviewQueue) {
    await reviewQueue.close();
    reviewQueue = null;
  }
  if (redisConnection) {
    await redisConnection.quit();
    redisConnection = null;
  }
}

module.exports = {
  getReviewQueue,
  addReviewJob,
  closeReviewQueue,
  getRedisConnection,
};
