"use strict";

/**
 * middleware/auth.middleware.js
 *
 * JWT authentication middleware.
 * Verifies the `auth_token` HTTP-only cookie and attaches the authenticated
 * user to `req.user` without exposing sensitive access tokens.
 */

const jwt = require("jsonwebtoken");
const { JWT_SECRET } = require("../config/env");
const { User } = require("../models");

/**
 * Middleware to authenticate requests via HTTP-only JWT cookie.
 */
async function authenticate(req, res, next) {
  try {
    const token = req.cookies?.auth_token;

    if (!token) {
      return res.status(401).json({
        error: "Unauthorized",
        message: "Authentication required",
      });
    }

    let decoded;
    try {
      decoded = jwt.verify(token, JWT_SECRET);
    } catch (jwtErr) {
      return res.status(401).json({
        error: "Unauthorized",
        message: "Invalid or expired token",
      });
    }

    if (!decoded || !decoded.sub) {
      return res.status(401).json({
        error: "Unauthorized",
        message: "Malformed authentication token",
      });
    }

    const user = await User.findByPk(decoded.sub);

    if (!user) {
      return res.status(401).json({
        error: "Unauthorized",
        message: "User not found",
      });
    }

    // Attach user information without exposing sensitive accessToken
    req.user = {
      id: user.id,
      githubId: user.githubId,
      username: user.username,
      connectedRepos: user.connectedRepos || [],
    };

    return next();
  } catch (err) {
    console.error("[Auth Middleware] Unexpected error during authentication:", err.message);
    return res.status(500).json({
      error: "Internal Server Error",
      message: "An error occurred during authentication verification",
    });
  }
}

module.exports = {
  authenticate,
};
