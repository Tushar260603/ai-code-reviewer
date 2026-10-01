"use strict";

/**
 * config/passport.js
 *
 * Passport.js configuration using GitHubStrategy.
 * Finds or creates a User in MySQL via Sequelize on successful authentication.
 * Never logs accessToken.
 */

const passport = require("passport");
const { Strategy: GitHubStrategy } = require("passport-github2");
const {
  GITHUB_CLIENT_ID,
  GITHUB_CLIENT_SECRET,
  GITHUB_CALLBACK_URL,
} = require("./env");
const { User } = require("../models");

const clientID = GITHUB_CLIENT_ID || "placeholder_client_id";
const clientSecret = GITHUB_CLIENT_SECRET || "placeholder_client_secret";

if (!GITHUB_CLIENT_ID || !GITHUB_CLIENT_SECRET) {
  console.warn(
    "[Passport] Warning: GITHUB_CLIENT_ID or GITHUB_CLIENT_SECRET is not configured in environment variables."
  );
}

passport.use(
  new GitHubStrategy(
    {
      clientID,
      clientSecret,
      callbackURL: GITHUB_CALLBACK_URL,
      scope: ["read:user", "user:email", "repo", "admin:repo_hook"],
    },
    async (accessToken, refreshToken, profile, done) => {
      try {
        const githubId = profile.id.toString();
        const username = profile.username || profile.displayName || `user-${githubId}`;

        // Find or create the user in MySQL using the stable GitHub ID
        const [user, created] = await User.findOrCreate({
          where: { githubId },
          defaults: {
            githubId,
            username,
            accessToken,
            connectedRepos: [],
          },
        });

        // If the user already exists, update their latest username and access token
        if (!created) {
          await user.update({
            username,
            accessToken,
          });
        }

        return done(null, user);
      } catch (err) {
        console.error("[Passport] Error finding or updating user:", err.message);
        return done(err, null);
      }
    }
  )
);

module.exports = passport;
