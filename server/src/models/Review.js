"use strict";

/**
 * models/Review.js
 *
 * One Review is created per AI review run for a given PullRequest + commit SHA.
 *
 * Idempotency: the composite unique index on (prId, triggeredBySha) prevents
 * the BullMQ worker from inserting a duplicate review when a job is retried.
 */

const { DataTypes } = require("sequelize");
const { getSequelizeInstance } = require("../config/db");

const sequelize = getSequelizeInstance();

const Review = sequelize.define(
  "Review",
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },

    prId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      references: { model: "pull_requests", key: "id" },
      onDelete: "CASCADE",
      onUpdate: "CASCADE",
      comment: "Foreign key → pull_requests.id",
    },

    triggeredBySha: {
      type: DataTypes.STRING(64),
      allowNull: false,
      comment: "Head commit SHA that triggered this review run",
    },

    verdict: {
      type: DataTypes.ENUM("approve", "request_changes", "comment"),
      allowNull: true,
      defaultValue: null,
      comment: "AI verdict: approve | request_changes | comment",
    },

    summary: {
      type: DataTypes.TEXT,
      allowNull: true,
      defaultValue: null,
      comment: "Human-readable summary produced by the supervisor agent",
    },
  },
  {
    tableName: "reviews",
    timestamps: true,
    updatedAt: false, // spec only mentions createdAt for this table
    indexes: [
      {
        // Idempotency: one review per (PR, SHA)
        unique: true,
        fields: ["prId", "triggeredBySha"],
      },
      { fields: ["prId"] },
      { fields: ["triggeredBySha"] },
    ],
  }
);

module.exports = Review;
