"use strict";

/**
 * routes/reviews.routes.js
 *
 * Authenticated endpoints for retrieving review history and findings:
 *   GET /api/reviews      - List recent reviews
 *   GET /api/reviews/:id  - Detailed review information with grouped findings
 */

const express = require("express");
const { authenticate } = require("../middleware/auth.middleware");
const {
  getRecentReviews,
  getReviewDetails,
  triggerManualReview,
  getReviewDiff,
} = require("../controllers/reviews.controller");

const router = express.Router();

// Authenticated review endpoints
router.get("/", authenticate, getRecentReviews);
router.post("/trigger", authenticate, triggerManualReview);
router.get("/:id", authenticate, getReviewDetails);
router.get("/:id/diff", authenticate, getReviewDiff);

module.exports = router;
