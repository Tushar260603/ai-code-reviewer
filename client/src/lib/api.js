import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000",
  withCredentials: true,
  timeout: 8000,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * Fetch authenticated user information.
 * Uses HTTP-only auth_token cookie automatically via withCredentials: true.
 */
export async function getCurrentUser() {
  const response = await api.get("/api/auth/me");
  return response.data;
}

/**
 * Fetch user repositories with connection status.
 */
export async function getRepos() {
  const response = await api.get("/api/repos");
  return response.data;
}

/**
 * Connect repository and auto-create webhook on GitHub.
 */
export async function connectRepo(repoFullName) {
  const response = await api.post("/api/repos/connect", { repoFullName });
  return response.data;
}

/**
 * Disconnect repository and auto-delete webhook on GitHub.
 */
export async function disconnectRepo(repoFullName) {
  const response = await api.post("/api/repos/disconnect", { repoFullName });
  return response.data;
}

/**
 * Fetch list of recent reviews.
 */
export async function getReviews() {
  const response = await api.get("/api/reviews");
  return response.data;
}

/**
 * Trigger an instant review on a PR manually.
 */
export async function triggerReview(repoFullName, prNumber) {
  const response = await api.post("/api/reviews/trigger", { repoFullName, prNumber });
  return response.data;
}

/**
 * Fetch review details by PR ID or Review ID.
 */
export async function getReview(id) {
  const response = await api.get(`/api/reviews/${id}`);
  return response.data;
}

/**
 * Fetch code diff and changed files for a review.
 */
export async function getReviewDiff(id) {
  const response = await api.get(`/api/reviews/${id}/diff`);
  return response.data;
}

/**
 * Fetch metrics data from the backend or fallback to mock if endpoint is pending.
 */
export async function getMetrics() {
  try {
    const response = await api.get("/api/metrics");
    return response.data;
  } catch (err) {
    // If backend doesn't implement /api/metrics yet, throw or handle in caller
    throw err;
  }
}

/**
 * Perform logout by clearing server-side cookie.
 */
export async function logout() {
  const response = await api.post("/api/auth/logout");
  return response.data;
}

export default api;

