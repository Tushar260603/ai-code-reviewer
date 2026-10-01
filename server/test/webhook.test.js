/**
 * webhook.test.js
 * Automated tests for the Express server and webhook pipeline.
 */

const { describe, it, before, after } = require("node:test");
const assert = require("node:assert");
const crypto = require("crypto");
const http = require("http");

// Configure test environment variables before loading app
process.env.PORT = "8005";
process.env.GITHUB_WEBHOOK_SECRET = "test_webhook_secret_key_12345";
process.env.MONGODB_URI = "mongodb://localhost:27017/ai-reviewer-test";
process.env.REDIS_URL = "redis://localhost:6379";

const { app } = require("../src/index");
const reviewQueueModule = require("../src/queues/review.queue");

// Helper to calculate valid GitHub HMAC-SHA256 signature
function calculateSignature(payloadString, secret) {
  const hmac = crypto.createHmac("sha256", secret);
  hmac.update(payloadString);
  return `sha256=${hmac.digest("hex")}`;
}

// Helper to make HTTP requests against the Express app
function makeRequest(server, options, body) {
  return new Promise((resolve, reject) => {
    const port = server.address().port;
    const reqOptions = {
      hostname: "127.0.0.1",
      port,
      path: options.path,
      method: options.method || "GET",
      headers: options.headers || {},
    };

    const req = http.request(reqOptions, (res) => {
      let rawData = "";
      res.on("data", (chunk) => {
        rawData += chunk;
      });
      res.on("end", () => {
        let json = null;
        try {
          json = JSON.parse(rawData);
        } catch (_) {}
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: json,
          raw: rawData,
        });
      });
    });

    req.on("error", reject);

    if (body) {
      req.write(body);
    }
    req.end();
  });
}

describe("Express Server & Webhook Suite", () => {
  let serverInstance = null;
  let originalAddReviewJob = null;
  const recordedJobs = [];

  before((_, done) => {
    // Mock review queue job submission so tests don't require a live Redis instance
    originalAddReviewJob = reviewQueueModule.addReviewJob;
    reviewQueueModule.addReviewJob = async (jobData, deliveryId) => {
      const job = { id: `mock-${deliveryId || Date.now()}`, data: jobData };
      recordedJobs.push({ jobData, deliveryId });
      return job;
    };

    serverInstance = app.listen(0, () => {
      done();
    });
  });

  after((_, done) => {
    reviewQueueModule.addReviewJob = originalAddReviewJob;
    if (serverInstance) {
      serverInstance.close(done);
    } else {
      done();
    }
  });

  it("GET /health returns 200 with healthy status", async () => {
    const res = await makeRequest(serverInstance, { path: "/health", method: "GET" });
    assert.strictEqual(res.statusCode, 200);
    assert.strictEqual(res.body.status, "healthy");
  });

  it("POST /api/webhook/github fails with 401 when signature header is missing", async () => {
    const payload = JSON.stringify({ action: "opened" });
    const res = await makeRequest(
      serverInstance,
      {
        path: "/api/webhook/github",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-GitHub-Event": "pull_request",
        },
      },
      payload
    );

    assert.strictEqual(res.statusCode, 401);
    assert.strictEqual(res.body.error, "Invalid webhook signature");
  });

  it("POST /api/webhook/github fails with 401 when signature is invalid", async () => {
    const payload = JSON.stringify({ action: "opened" });
    const res = await makeRequest(
      serverInstance,
      {
        path: "/api/webhook/github",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Hub-Signature-256": "sha256=invalid_hex_signature_000000000000000000000000000000000000",
          "X-GitHub-Event": "pull_request",
        },
      },
      payload
    );

    assert.strictEqual(res.statusCode, 401);
    assert.strictEqual(res.body.error, "Invalid webhook signature");
  });

  it("POST /api/webhook/github ignores non-pull_request events with 200", async () => {
    const payload = JSON.stringify({ ref: "refs/heads/main" });
    const signature = calculateSignature(payload, process.env.GITHUB_WEBHOOK_SECRET);

    const res = await makeRequest(
      serverInstance,
      {
        path: "/api/webhook/github",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Hub-Signature-256": signature,
          "X-GitHub-Event": "push",
          "X-GitHub-Delivery": "delivery-push-1",
        },
      },
      payload
    );

    assert.strictEqual(res.statusCode, 200);
    assert.strictEqual(res.body.status, "ignored");
  });

  it("POST /api/webhook/github ignores unsupported actions (e.g. 'closed') with 200", async () => {
    const payload = JSON.stringify({
      action: "closed",
      pull_request: { number: 42 },
      repository: { full_name: "test/repo" },
    });
    const signature = calculateSignature(payload, process.env.GITHUB_WEBHOOK_SECRET);

    const res = await makeRequest(
      serverInstance,
      {
        path: "/api/webhook/github",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Hub-Signature-256": signature,
          "X-GitHub-Event": "pull_request",
          "X-GitHub-Delivery": "delivery-closed-1",
        },
      },
      payload
    );

    assert.strictEqual(res.statusCode, 200);
    assert.strictEqual(res.body.status, "ignored");
  });

  it("POST /api/webhook/github successfully enqueues 'opened' PR event", async () => {
    const payloadObj = {
      action: "opened",
      pull_request: {
        number: 101,
        html_url: "https://github.com/my-org/my-repo/pull/101",
        diff_url: "https://github.com/my-org/my-repo/pull/101.diff",
        base: { sha: "base_sha_123" },
        head: { sha: "head_sha_456" },
      },
      repository: {
        full_name: "my-org/my-repo",
        clone_url: "https://github.com/my-org/my-repo.git",
        html_url: "https://github.com/my-org/my-repo",
      },
      sender: {
        login: "octocat",
      },
    };

    const payload = JSON.stringify(payloadObj);
    const signature = calculateSignature(payload, process.env.GITHUB_WEBHOOK_SECRET);
    const deliveryId = "deliv-pr-opened-101";

    const res = await makeRequest(
      serverInstance,
      {
        path: "/api/webhook/github",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Hub-Signature-256": signature,
          "X-GitHub-Event": "pull_request",
          "X-GitHub-Delivery": deliveryId,
        },
      },
      payload
    );

    assert.strictEqual(res.statusCode, 200);
    assert.strictEqual(res.body.status, "queued");
    assert.strictEqual(res.body.pr_number, 101);
    assert.strictEqual(res.body.delivery_id, deliveryId);

    // Verify metadata was extracted and queued properly
    const queuedJob = recordedJobs.find((j) => j.deliveryId === deliveryId);
    assert.ok(queuedJob, "Job should have been passed to addReviewJob");
    assert.strictEqual(queuedJob.jobData.prNumber, 101);
    assert.strictEqual(queuedJob.jobData.repoFullName, "my-org/my-repo");
    assert.strictEqual(queuedJob.jobData.baseSha, "base_sha_123");
    assert.strictEqual(queuedJob.jobData.headSha, "head_sha_456");
    assert.strictEqual(queuedJob.jobData.action, "opened");
    assert.strictEqual(queuedJob.jobData.sender, "octocat");
  });

  it("POST /api/webhook/github successfully enqueues 'synchronize' PR event", async () => {
    const payloadObj = {
      action: "synchronize",
      pull_request: {
        number: 101,
        html_url: "https://github.com/my-org/my-repo/pull/101",
        diff_url: "https://github.com/my-org/my-repo/pull/101.diff",
        base: { sha: "base_sha_123" },
        head: { sha: "new_head_sha_789" },
      },
      repository: {
        full_name: "my-org/my-repo",
        clone_url: "https://github.com/my-org/my-repo.git",
      },
    };

    const payload = JSON.stringify(payloadObj);
    const signature = calculateSignature(payload, process.env.GITHUB_WEBHOOK_SECRET);
    const deliveryId = "deliv-pr-sync-102";

    const res = await makeRequest(
      serverInstance,
      {
        path: "/api/webhook/github",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Hub-Signature-256": signature,
          "X-GitHub-Event": "pull_request",
          "X-GitHub-Delivery": deliveryId,
        },
      },
      payload
    );

    assert.strictEqual(res.statusCode, 200);
    assert.strictEqual(res.body.status, "queued");
    assert.strictEqual(res.body.pr_number, 101);

    const queuedJob = recordedJobs.find((j) => j.deliveryId === deliveryId);
    assert.ok(queuedJob);
    assert.strictEqual(queuedJob.jobData.headSha, "new_head_sha_789");
    assert.strictEqual(queuedJob.jobData.action, "synchronize");
  });
});
