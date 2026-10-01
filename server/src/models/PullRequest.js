"use strict";

/**
 * models/PullRequest.js
 *
 * Represents a GitHub Pull Request tracked for AI code review.
 *
 * Composite unique index on (repoFullName, prNumber) ensures that
 * owner/repo-a#10 and owner/repo-b#10 are stored as separate rows.
 */

const { DataTypes } = require("sequelize");
const { getSequelizeInstance } = require("../config/db");

const sequelize = getSequelizeInstance();

const PullRequest = sequelize.define(
  "PullRequest",
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },

    repoFullName: {
      type: DataTypes.STRING(255),
      allowNull: false,
      comment: 'GitHub repository full name, e.g. "owner/repo"',
    },

    prNumber: {
      type: DataTypes.INTEGER,
      allowNull: false,
      comment: "Pull request number within the repository",
    },

    title: {
      type: DataTypes.STRING(512),
      allowNull: true,
      defaultValue: null,
    },

    author: {
      type: DataTypes.STRING(255),
      allowNull: true,
      defaultValue: null,
      comment: "GitHub username of the PR author",
    },

    status: {
      type: DataTypes.STRING(64),
      allowNull: false,
      defaultValue: "pending",
      comment: "pending | reviewing | completed | failed",
    },

    lastReviewedSha: {
      type: DataTypes.STRING(64),
      allowNull: true,
      defaultValue: null,
      comment: "Head commit SHA of the most recently reviewed push",
    },
  },
  {
    tableName: "pull_requests",
    timestamps: true, // createdAt, updatedAt
    indexes: [
      {
        // Primary lookup — also enforces uniqueness across repos
        unique: true,
        fields: ["repoFullName", "prNumber"],
      },
      {
        // Fast status filtering
        fields: ["status"],
      },
    ],
  }
);

module.exports = PullRequest;
