"use strict";

/**
 * controllers/repos.controller.js
 *
 * Handles repository listing and automatic 1-click webhook connection.
 */

const { User } = require("../models");
const {
  listUserRepos,
  createRepoWebhook,
  deleteRepoWebhook,
} = require("../services/githubClient");
const {
  WEBHOOK_PAYLOAD_URL,
  GITHUB_WEBHOOK_SECRET,
} = require("../config/env");

/**
 * GET /api/repos
 * Lists repositories belonging to the authenticated user and flags connected status.
 */
async function getRepos(req, res, next) {
  try {
    const user = await User.findByPk(req.user.id);
    if (!user) {
      return res.status(404).json({ error: "User not found" });
    }

    if (!user.accessToken) {
      return res.status(400).json({
        error: "Missing GitHub Access Token",
        message: "Please re-login with GitHub to grant repository access permissions.",
        repos: [],
        connectedRepos: user.connectedRepos || [],
      });
    }

    const connected = Array.isArray(user.connectedRepos) ? user.connectedRepos : [];
    const repos = await listUserRepos(user.accessToken);

    const enriched = repos.map((repo) => ({
      ...repo,
      isConnected: connected.includes(repo.fullName),
    }));

    return res.status(200).json({
      repos: enriched,
      connectedRepos: connected,
      webhookUrl: WEBHOOK_PAYLOAD_URL,
    });
  } catch (err) {
    console.error("[ReposController] Error listing repos:", err.message);
    return res.status(500).json({
      error: "Failed to fetch repositories",
      message: err.message,
    });
  }
}

/**
 * POST /api/repos/connect
 * Automatically installs the webhook on the requested repository via GitHub API
 * and adds it to the user's connectedRepos list.
 */
async function connectRepo(req, res, next) {
  try {
    const { repoFullName } = req.body;
    if (!repoFullName || typeof repoFullName !== "string" || !repoFullName.includes("/")) {
      return res.status(400).json({
        error: "Invalid Request",
        message: "A valid repository full name ('owner/repo') is required.",
      });
    }

    const user = await User.findByPk(req.user.id);
    if (!user) {
      return res.status(404).json({ error: "User not found" });
    }

    if (!user.accessToken) {
      return res.status(401).json({
        error: "Unauthorized",
        message: "GitHub token missing. Please log in with GitHub.",
      });
    }

    // 1. Call GitHub API to create/verify webhook
    const result = await createRepoWebhook(
      repoFullName,
      WEBHOOK_PAYLOAD_URL,
      GITHUB_WEBHOOK_SECRET,
      user.accessToken
    );

    // 2. Add to connectedRepos in database
    const currentList = Array.isArray(user.connectedRepos) ? [...user.connectedRepos] : [];
    if (!currentList.includes(repoFullName)) {
      currentList.push(repoFullName);
      await user.update({ connectedRepos: currentList });
    }

    return res.status(200).json({
      success: true,
      message: result.alreadyExists
        ? `Repository ${repoFullName} connected (webhook was already active).`
        : `Repository ${repoFullName} connected and webhook created successfully!`,
      repoFullName,
      connectedRepos: currentList,
      hookId: result.hook?.id,
    });
  } catch (err) {
    console.error("[ReposController] Error connecting repo:", err.message);

    let friendlyMessage = err.message;
    if (
      err.message.includes("422") ||
      (WEBHOOK_PAYLOAD_URL && WEBHOOK_PAYLOAD_URL.includes("localhost"))
    ) {
      friendlyMessage =
        "GitHub cannot send webhooks to 'localhost'. Please start a tunnel (run: npx localtunnel --port 5000) and add WEBHOOK_PAYLOAD_URL=https://<your-tunnel-url>/api/webhook/github in server/.env";
    }

    return res.status(400).json({
      error: "Failed to connect repository",
      message: friendlyMessage,
    });
  }
}

/**
 * POST /api/repos/disconnect
 * Automatically removes the webhook from GitHub and updates connectedRepos.
 */
async function disconnectRepo(req, res, next) {
  try {
    const { repoFullName } = req.body;
    if (!repoFullName) {
      return res.status(400).json({
        error: "Invalid Request",
        message: "Repository full name is required.",
      });
    }

    const user = await User.findByPk(req.user.id);
    if (!user) {
      return res.status(404).json({ error: "User not found" });
    }

    // 1. Remove webhook from GitHub (best effort)
    if (user.accessToken) {
      try {
        await deleteRepoWebhook(repoFullName, WEBHOOK_PAYLOAD_URL, user.accessToken);
      } catch (ghErr) {
        console.warn(
          `[ReposController] Could not delete webhook from GitHub for ${repoFullName}:`,
          ghErr.message
        );
      }
    }

    // 2. Remove from connectedRepos in DB
    const currentList = Array.isArray(user.connectedRepos) ? [...user.connectedRepos] : [];
    const updatedList = currentList.filter((r) => r !== repoFullName);
    await user.update({ connectedRepos: updatedList });

    return res.status(200).json({
      success: true,
      message: `Repository ${repoFullName} disconnected.`,
      repoFullName,
      connectedRepos: updatedList,
    });
  } catch (err) {
    console.error("[ReposController] Error disconnecting repo:", err.message);
    return res.status(500).json({
      error: "Failed to disconnect repository",
      message: err.message,
    });
  }
}

module.exports = {
  getRepos,
  connectRepo,
  disconnectRepo,
};
