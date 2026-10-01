"use strict";

/**
 * routes/auth.routes.js
 *
 * Authentication routes:
 *   GET  /api/auth/github          - Initiates GitHub OAuth
 *   GET  /api/auth/github/callback - Handles GitHub OAuth callback and sets JWT cookie
 *   GET  /api/auth/me              - Returns currently authenticated user (protected)
 *   POST /api/auth/logout          - Clears authentication cookie
 */

const express = require("express");
const passport = require("passport");
const jwt = require("jsonwebtoken");
const {
  JWT_SECRET,
  JWT_EXPIRES_IN,
  FRONTEND_URL,
  NODE_ENV,
} = require("../config/env");
const { authenticate } = require("../middleware/auth.middleware");

const router = express.Router();

/**
 * GET /api/auth/github
 * Start GitHub OAuth authorization flow.
 */
router.get(
  "/github",
  passport.authenticate("github", {
    scope: ["read:user", "user:email", "repo", "admin:repo_hook"],
    session: false,
  })
);

/**
 * GET /api/auth/github/callback
 * GitHub OAuth callback: handles token exchange, issues JWT, sets HTTP-only cookie,
 * and redirects to the frontend.
 */
router.get(
  "/github/callback",
  passport.authenticate("github", {
    session: false,
    failureRedirect: `${FRONTEND_URL}/login?error=github_auth_failed`,
  }),
  (req, res) => {
    try {
      const user = req.user;

      if (!user) {
        return res.redirect(`${FRONTEND_URL}/login?error=user_not_found`);
      }

      // Generate JWT without sensitive accessToken
      const token = jwt.sign(
        {
          sub: user.id,
          githubId: user.githubId,
          username: user.username,
        },
        JWT_SECRET,
        {
          expiresIn: JWT_EXPIRES_IN || "7d",
        }
      );

      // Set JWT in HTTP-only cookie
      res.cookie("auth_token", token, {
        httpOnly: true,
        secure: NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days in ms
      });

      // Redirect to frontend dashboard
      return res.redirect(`${FRONTEND_URL}/`);
    } catch (err) {
      console.error("[Auth Routes] Error during OAuth callback processing:", err.message);
      return res.redirect(`${FRONTEND_URL}/login?error=server_error`);
    }
  }
);

/**
 * GET /api/auth/me
 * Returns information for currently authenticated user.
 */
router.get("/me", authenticate, (req, res) => {
  return res.status(200).json({
    id: req.user.id,
    githubId: req.user.githubId,
    username: req.user.username,
    connectedRepos: req.user.connectedRepos || [],
  });
});

/**
 * POST /api/auth/logout
 * Clears the auth_token cookie.
 */
router.post("/logout", (req, res) => {
  res.clearCookie("auth_token", {
    httpOnly: true,
    secure: NODE_ENV === "production",
    sameSite: "lax",
  });

  return res.status(200).json({
    message: "Logged out successfully",
  });
});

module.exports = router;
