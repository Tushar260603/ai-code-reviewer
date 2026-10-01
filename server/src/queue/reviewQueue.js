/**
 * reviewQueue.js
 * Alias re-export for queues/review.queue.js.
 */

const {
  getReviewQueue,
  addReviewJob,
  closeReviewQueue,
  getRedisConnection,
} = require("../queues/review.queue");

module.exports = {
  getReviewQueue,
  addReviewJob,
  closeReviewQueue,
  getRedisConnection,
};
