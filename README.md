# NGO Transparency Platform

> **Evidence-Based NGO Fund Utilization Transparency & Trust Platform**
> SIH Prototype — Foundation Release v0.1.0

---

## What This Platform Does

This is an evidence-based verification and transparency platform for NGO-funded projects. It is **not** a donation platform or a rating system.

**Core flow:**
```
NGO creates project (location registered via map)
→ NGO submits geo-tagged, timestamped evidence
→ System captures metadata (not manual lat/lon)
→ Automated verification checks run
→ Risk engine flags inconsistencies
→ Selected projects are independently audited
→ Project Evidence Score is calculated (server-side)
→ NGO Transparency Score is derived (weighted composite)
→ Donors see transparent project-level evidence and scores
```

**What it does NOT claim:**
- It does not prove NGO honesty
- It does not verify every rupee
- It does not require volunteers at every site
- Scores are explainable, not magic

---

## Architecture

```
frontend/          React + TypeScript + Tailwind CSS (Vite)
backend/           Python + FastAPI
  app/
    auth/          User model, JWT auth, RBAC
    projects/      Project Service
    evidence/      Evidence Service (Phase 2)
    verification/  Verification Engine (Phase 3)
    audit/         Audit Service (Phase 4)
    scores/        Score Engine (Phase 4)
    core/          Shared: responses, exceptions, security, logging
  alembic/         Database migrations
database/          PostgreSQL 16 + PostGIS 3
```

### User Roles

| Role     | Access                                         |
|----------|------------------------------------------------|
| NGO      | Create projects, submit evidence               |
| DONOR    | Browse public projects and scores              |
| AUDITOR  | Review assigned projects, submit audit decisions |
| ADMIN    | Full platform access, user management          |

### API Conventions

All responses follow this envelope:

**Success:**
```json
{
  "success": true,
  "data": { ... },
  "message": "Optional message"
}
```

**Error:**
```json
{
  "success": false,
  "error": "Human-readable error",
  "details": [{ "field": "email", "message": "Already exists" }]
}
```

All scores are calculated **server-side only**. NGOs cannot modify verification results, audit decisions, or scores.

---

## Project Evidence Score

| Component             | Max Points |
|-----------------------|-----------|
| Location consistency  | 20        |
| Timeline / timestamp  | 15        |
| Media evidence        | 20        |
| Financial evidence    | 20        |
| Project identity      | 10        |
| Independent audit     | 15        |
| **Total**             | **100**   |

**NGO Transparency Score** is a weighted composite of project Evidence Scores, project values, verification status, audit history, and disputes. It is **not** `verified / total`.

---

## Development Setup

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for PostgreSQL + PostGIS)
- [Python 3.12+](https://www.python.org/downloads/)
- [Node.js 20+](https://nodejs.org/)

### 1. Clone and configure

```bash
# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Edit backend/.env — set JWT_SECRET_KEY to a random string
```

### 2. Start the database (Docker)

```bash
# Start only the database container
docker compose up db -d

# Or start everything (db + backend + frontend)
docker compose up -d
```

### 3. Backend setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the dev server
uvicorn app.main:app --reload --port 8000
```

Backend will be available at: **http://localhost:8000**
API docs (Swagger UI): **http://localhost:8000/docs**

### 4. Frontend setup

```bash
cd frontend

npm install
npm run dev
```

Frontend will be available at: **http://localhost:5173**

---

## Environment Variables

### Backend (`backend/.env`)

| Variable                    | Description                              | Required |
|-----------------------------|------------------------------------------|----------|
| `DATABASE_URL`              | Async PostgreSQL URL (asyncpg driver)    | ✅       |
| `SYNC_DATABASE_URL`         | Sync PostgreSQL URL (for Alembic)        | ✅       |
| `JWT_SECRET_KEY`            | Long random string for JWT signing       | ✅       |
| `JWT_ALGORITHM`             | HS256 (default)                          | ✅       |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Default: 60                            |          |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Default: 30                              |          |
| `CORS_ORIGINS`              | Comma-separated allowed origins          |          |
| `STORAGE_BACKEND`           | `local` (dev) or `s3` (prod)            |          |
| `ADMIN_EMAIL`               | Seed admin account email                 |          |
| `ADMIN_PASSWORD`            | Seed admin account password              |          |

### Frontend (`frontend/.env`)

| Variable            | Description                      |
|---------------------|----------------------------------|
| `VITE_API_BASE_URL` | Backend API base URL             |
| `VITE_APP_NAME`     | App display name                 |

---

## Database Migrations

```bash
# Create a new migration (auto-detect changes)
alembic revision --autogenerate -m "description"

# Apply all migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1
```

---

## Project Types

- Infrastructure
- Education
- Food Distribution
- Healthcare
- Sanitation
- Environment
- Relief Distribution

## Verification Models

| Model               | Flow                                                                 |
|---------------------|----------------------------------------------------------------------|
| Permanent           | Before → Progress → Completion                                       |
| One-Time Event      | Registration → Evidence → Time/Location Verification → Confirmation  |
| Financial Assistance| Documentary/financial verification with privacy protection           |

---

## Important Domain Rules

1. **NGO registered location ≠ project location.** Never compare evidence against NGO office location.
2. Evidence location is compared against **project registered location** only.
3. NGOs use map selection or GPS — no manual lat/lon text input.
4. GPS is one verification signal, not the only one.
5. Evidence submission ≠ automatic verification.
6. Evidence history is append-only — no silent overwriting.
7. Scores and verification results are server-side only.
8. All important actions generate audit logs.

---

## Remaining Phases

| Phase | Features                                                             |
|-------|----------------------------------------------------------------------|
| **2** | Evidence submission (geo-tagged media, financial docs), Project management UI, Map integration |
| **3** | Verification engine (location consistency, timestamp checks, duplicate detection), Risk Engine |
| **4** | Score Engine (Project Evidence Score, NGO Transparency Score), Audit assignment workflow, Auditor portal |
| **5** | Donor-facing project explorer, public transparency dashboard, NGO profile pages |
| **6** | AI/ML features (image similarity, OCR, anomaly detection) — modular, explainable |
| **7** | Production hardening, S3 storage, monitoring, performance optimization |

---

## API Endpoints (v0.1.0)

| Method | Path                    | Auth         | Description                    |
|--------|-------------------------|--------------|--------------------------------|
| POST   | `/api/v1/auth/register` | Public       | Register NGO/Donor/Auditor     |
| POST   | `/api/v1/auth/login`    | Public       | Get JWT token pair             |
| POST   | `/api/v1/auth/refresh`  | Public       | Refresh access token           |
| GET    | `/api/v1/auth/me`       | Any role     | Get current user profile       |
| GET    | `/api/v1/projects/`     | Public       | List public projects           |
| POST   | `/api/v1/projects/`     | NGO, Admin   | Create project                 |
| GET    | `/api/v1/projects/my`   | NGO, Admin   | List own projects              |
| GET    | `/api/v1/projects/{id}` | Public       | Get project detail             |
| GET    | `/health`               | Public       | Health check                   |

---

*Built for Smart India Hackathon (SIH). This is a prototype.*
