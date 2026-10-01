"use strict";

/**
 * routes/repos.routes.js
 *
 * Repository management routes:
 *   GET  /api/repos            - List all user repositories with connection status
 *   POST /api/repos/connect    - 1-click connect repo & auto-create webhook on GitHub
 *   POST /api/repos/disconnect - Disconnect repo & remove webhook from GitHub
 */

const express = require("express");
const { authenticate } = require("../middleware/auth.middleware");
const {
  getRepos,
  connectRepo,
  disconnectRepo,
} = require("../controllers/repos.controller");

const router = express.Router();

router.use(authenticate);

router.get("/", getRepos);
router.post("/connect", connectRepo);
router.post("/disconnect", disconnectRepo);

module.exports = router;
