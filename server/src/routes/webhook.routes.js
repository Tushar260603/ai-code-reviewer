/**
 * webhook.routes.js
 * Routes for incoming webhooks.
 *
 * Mounted under /api/webhook in index.js:
 * POST /api/webhook/github
 */

const express = require("express");
const verifyWebhook = require("../middleware/verifyWebhook");
const { handleGitHubWebhook } = require("../controllers/webhook.controller");

const router = express.Router();

/**
 * @route   POST /api/webhook/github
 * @desc    Receive and verify GitHub pull_request webhooks, then enqueue for review
 * @access  Public (protected via HMAC-SHA256 signature verification)
 */
router.post("/github", verifyWebhook, handleGitHubWebhook);

module.exports = router;
