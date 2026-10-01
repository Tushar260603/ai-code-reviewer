<div align="center">

# 🤖 Autonomous AI Code Reviewer

### *Production-Grade Multi-Agent Code Analysis for GitHub Pull Requests*

[![Next.js](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![Node.js](https://img.shields.io/badge/Node.js-20.x-green?style=for-the-badge&logo=node.js)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python)](https://python.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-3.1%20Flash%20Lite-4285F4?style=for-the-badge&logo=google)](https://ai.google.dev/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql)](https://mysql.com/)
[![TailwindCSS](https://img.shields.io/badge/Tailwind-3.4-38B2AC?style=for-the-badge&logo=tailwind-css)](https://tailwindcss.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

<br />

**An intelligent, multi-agent code review platform that inspects GitHub Pull Requests in real time, flags security vulnerabilities, detects logical bugs and code cleanliness anti-patterns, stores line-by-line findings in MySQL, and automatically posts review verdicts back onto GitHub.**

[Explore Architecture](#-system-architecture) •
[Specialized Agents](#-specialized-agents) •
[Quickstart](#-getting-started) •
[API Reference](#-api-endpoints) •
[Database Schema](#-database-schema)

</div>

---

## 🌟 Key Features

* **🛡️ Tri-Agent Specialized Review Pipeline:** Instead of a generic prompt, dedicated agents (**Security**, **Style**, and **Logic**) review code independently for maximum precision and minimal hallucination.
* **⚡ Sub-10-Second Reviews:** Direct structured output generation delivers full multi-agent evaluations within **~8 to 10 seconds** without hitting rate limits.
* **🔄 Dual Review Triggers:**
  * **Automated Webhooks:** Listens to GitHub `pull_request` events (`opened`, `synchronize`) on every `git push`.
  * **Interactive Dashboard:** Manual on-demand review trigger via Next.js web console with real-time progress polling.
* **💬 Automated GitHub Comments:** Synthesizes markdown review reports directly into the GitHub PR conversation thread.
* **🔒 Idempotent & Rate-Limit Optimized:** Prevents duplicate runs for the same commit SHA, saving token costs and preventing redundant reviews.
* **📊 Comprehensive Analytics Dashboard:** Next.js dashboard featuring visual charts, severity badges (`Critical`, `High`, `Medium`, `Low`), diff inspection, and 1-click issue resolution.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph ClientLayer["🖥️ Frontend (Port 3000)"]
        UI["Next.js Dashboard\n(/dashboard)"]
    end

    subgraph BackendLayer["⚙️ Backend Server (Port 5000)"]
        Express["Express Server\n(src/index.js)"]
        ReviewsCtrl["Reviews Controller\n(reviews.controller.js)"]
        Worker["Review Worker\n(queue/reviewWorker.js)"]
        Webhook["Webhook Controller\n(webhook.controller.js)"]
    end

    subgraph DatabaseLayer["💾 Database (Port 3306)"]
        MySQL[("MySQL Database\n(aireview)\n- pull_requests\n- reviews\n- findings")]
    end

    subgraph ExternalServices["🌐 External Integrations"]
        GitHub["GitHub API / PR\n(Diffs, Commits, Comments)"]
        Gemini["Google Gemini API\n(gemini-3.1-flash-lite)"]
    end

    subgraph AgentLayer["🤖 AI Agent Service (Port 8000)"]
        FastAPI["FastAPI App\n(app/main.py)"]
        Supervisor["ReviewSupervisor\n(app/agents/supervisor.py)"]
        SecAgent["SecurityAgent\n(Secrets, Injection, Auth)"]
        StyleAgent["StyleAgent\n(Cleanliness, Dead Code)"]
        LogicAgent["LogicAgent\n(Bugs, Edge Cases, Perf)"]
    end

    %% Manual Trigger Flow
    UI -->|"1. POST /api/reviews/trigger"| ReviewsCtrl
    ReviewsCtrl -->|"2. 202 Accepted (Instant)"| UI
    ReviewsCtrl -->|"3. Dispatches background job"| Worker

    %% Webhook Flow
    GitHub -.->|"Alternative: Webhook PR Event"| Webhook
    Webhook -.->|"Queue review job"| Worker

    %% Worker Execution
    Worker -->|"4. Fetches PR diff & metadata"| GitHub
    Worker -->|"5. POST /review with PR diff"| FastAPI

    %% Agent Pipeline
    FastAPI --> Supervisor
    Supervisor -->|"6a. Analyze security"| SecAgent
    Supervisor -->|"6b. Analyze style"| StyleAgent
    Supervisor -->|"6c. Analyze logic"| LogicAgent

    SecAgent -->|"7a. Structured prompt"| Gemini
    StyleAgent -->|"7b. Structured prompt"| Gemini
    LogicAgent -->|"7c. Structured prompt"| Gemini

    Gemini -->|"8. Return findings JSON"| Supervisor
    Supervisor -->|"9. Deduplicate & calculate verdict"| FastAPI
    FastAPI -->|"10. Return ReviewResult"| Worker

    %% Persistence & UI Update
    Worker -->|"11. Save review & findings"| MySQL
    Worker -->|"12. Post AI review comment"| GitHub
    UI -->|"13. Auto-poll GET /api/reviews"| Express
    Express -->|"14. Read latest results"| MySQL
    Express -->|"15. Return findings & verdict"| UI
```

---

## 🤖 Specialized Agents

| Agent | Focus Area | Example Bugs Detected |
| :--- | :--- | :--- |
| **🛡️ SecurityAgent** | Application Security & Credentials | Plaintext passwords/tokens, SQL injection, IDOR, sensitive data leakage, dangerous deserialization |
| **🎨 StyleAgent** | Code Hygiene & Standards | Accidental debug text / keyboard smash, deprecated variables (`var` vs `const`), dead code, naming violations |
| **🧠 LogicAgent** | Correctness, Edge Cases & Performance | Inverted boolean conditions, off-by-one errors, missing null/undefined checks, infinite loops, N+1 query patterns |
| **👔 ReviewSupervisor** | Orchestration & Deduplication | Aggregates specialist reports, deduplicates overlapping issues, calculates final verdict (`approve` vs `request_changes`) |

---

## 🗄️ Database Schema

The system uses **MySQL** managed via **Sequelize ORM**:

```text
users ───< (OAuth & Connected Repos)
             │
pull_requests ───< reviews ───< findings
(PR Metadata)      (Verdict,     (Line-by-line Issues,
                    Summary)      Severity, Resolved Status)
```

* **`users`**: Stores GitHub OAuth profiles, encrypted access tokens, and tracked repository lists.
* **`pull_requests`**: Tracks repository full name, PR number, author, current status (`pending`, `reviewing`, `completed`), and latest reviewed commit SHA.
* **`reviews`**: One record per commit evaluation. Stores `verdict` (`approve`, `request_changes`, `comment`), high-level AI summary, and composite unique key `(prId, triggeredBySha)`.
* **`findings`**: Line-by-line issues with `file`, 1-based `line` number, `severity` (`critical`, `high`, `medium`, `low`), `agentType`, actionable fix `message`, and `resolved` boolean toggle.

---

## 🚀 Getting Started

### Prerequisites

Ensure you have installed:
* [Node.js](https://nodejs.org/) (v18.x or v20.x+)
* [Python](https://www.python.org/) (v3.11+ or v3.12+)
* [MySQL](https://www.mysql.com/) (v8.0+)
* A [Google Gemini API Key](https://ai.google.dev/)
* A [GitHub Personal Access Token](https://github.com/settings/tokens) (with `repo` permissions)

---

### Step 1: Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/AI-Reviewer-PROJECT.git
cd AI-Reviewer-PROJECT
```

---

### Step 2: Configure Environment Variables

#### 1. Backend Server (`server/.env`)
Create `server/.env` based on `server/.env.example`:
```env
PORT=5000
NODE_ENV=development

# MySQL Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=aireview

# FastAPI Agent Service
FASTAPI_URL=http://localhost:8000

# GitHub Configuration
GITHUB_TOKEN=ghp_your_github_personal_access_token
GITHUB_WEBHOOK_SECRET=your_webhook_secret
WEBHOOK_PAYLOAD_URL=http://localhost:5000/api/webhook/github

# GitHub OAuth (Optional for local development)
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_CALLBACK_URL=http://localhost:5000/api/auth/github/callback

# JWT & Frontend
JWT_SECRET=your_jwt_secret_key
FRONTEND_URL=http://localhost:3000
```

#### 2. AI Agent Service (`agent-service/.env`)
Create `agent-service/.env`:
```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.1-flash-lite
PORT=8000
```

---

### Step 3: Start Services (3 Terminals)

#### Terminal 1: Python AI Agent Service
```powershell
cd agent-service
python -m venv .venv
.\.venv\Scripts\activate       # On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
> **Verify:** Navigate to `http://localhost:8000/health` → `{"status": "healthy"}`

#### Terminal 2: Node.js Express Backend
```powershell
cd server
npm install
npm run dev
```
> **Verify:** Navigate to `http://localhost:5000/health` → `{"status": "healthy"}`

#### Terminal 3: Next.js Client Dashboard
```powershell
cd client
npm install
npm run dev
```
> **Verify:** Open [http://localhost:3000/dashboard](http://localhost:3000/dashboard) in your browser.

---

## ⚡ How to Run a Code Review

### Method A: Via Web Dashboard (Instant Manual Review)
1. Open `http://localhost:3000/dashboard`.
2. Click **"⚡ Review PR Now"** in the top navigation bar.
3. Enter your repository (`owner/repo`) and PR Number (e.g. `1`).
4. Click **"Start Review"**.
5. The dashboard will show an instant loading banner and auto-poll every 2.5 seconds. Results appear within **~8 to 10 seconds**!

### Method B: Automated GitHub Push (Webhook)
1. In your GitHub repository, navigate to **Settings** → **Webhooks** → **Add Webhook**.
2. Set **Payload URL** to your server endpoint (use [ngrok](https://ngrok.com/) or [localtunnel](https://localtunnel.me/) for local development):
   `https://your-tunnel.loca.lt/api/webhook/github`
3. Content type: `application/json`.
4. Secret: Same as `GITHUB_WEBHOOK_SECRET` in `server/.env`.
5. Events: Select **"Let me select individual events"** → Check **Pull requests**.
6. Every time code is pushed or a PR is opened, the review runs automatically and comments on GitHub!

---

## 📡 API Endpoints

### Backend Server (`localhost:5000`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Server health check |
| `POST` | `/api/reviews/trigger` | Triggers on-demand manual PR review (Returns `202 Accepted`) |
| `GET` | `/api/reviews` | Lists all historical code reviews |
| `GET` | `/api/reviews/:prId` | Fetches detailed review report and line findings |
| `GET` | `/api/reviews/:prId/diff` | Fetches cached GitHub git diff for visual comparison |
| `PATCH`| `/api/reviews/findings/:id/resolve` | Toggles finding resolution status (`resolved: true/false`) |
| `POST` | `/api/webhook/github` | Handles GitHub pull request delivery events |

### Agent Service (`localhost:8000`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status |
| `POST` | `/review` | Accepts PR diff & changed files, returns structured `ReviewResponse` |

---

## 🛠️ Tech Stack Breakdown

* **Frontend:** Next.js 14, React 18, TailwindCSS, Recharts (visual trend metrics), Axios.
* **Backend:** Node.js, Express.js 5, Sequelize ORM, MySQL2, Passport.js (GitHub Strategy), JWT.
* **Agentic AI:** Python 3.12, FastAPI, LangChain, Google GenAI SDK (`gemini-3.1-flash-lite`), Pydantic v2.
* **DevOps & Tooling:** Nodemon, Uvicorn, LocalTunnel, Git.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) — see the LICENSE file for details.
