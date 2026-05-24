# ProConnect — Local Development Setup Guide

Welcome to the **ProConnect** developer onboarding guide. Follow these instructions to get your local environment running.

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed on your machine:

1. **Docker Desktop** (v24.0.0+ recommended)
2. **Git**
3. **Make** (optional, for utilizing the `Makefile` shortcuts)
4. **Python 3.12** (if you want to run tests/linting outside of Docker)

---

## 🚀 Quick Start (Docker Environment)

We run the entire system — PostgreSQL, Redis, FastAPI, Celery, Flower, Nginx, and Next.js — within Docker Compose to guarantee environment parity with production.

### Step 1: Clone the Repository & Enter Workspace

```bash
git clone <your-repo-url> proconnect
cd proconnect/ProConnect
```

### Step 2: Configure Environment Variables

Create your local environment files by copying the templates:

```bash
# In the ProConnect/ directory:
cp .env.example .env
cp .env.dev.example .env.dev

# In the frontend directory:
cp frontend/.env.example frontend/.env.local
```

> [!NOTE]
> For standard local development, the default values in `.env.dev.example` are pre-configured to connect to the internal Docker services. You do not need to change them.

### Step 3: Boot the Environment

Using the Makefile:
```bash
make dev
```
*Or directly via Docker Compose:*
```bash
docker compose -f docker-compose.dev.yml up --build
```

This command will:
- Spin up a PostgreSQL database on port `5432`
- Start Redis on port `6379`
- Build and launch the Next.js frontend on port `3000`
- Build and launch the FastAPI backend on port `8000`
- Start the Celery Worker + Celery Beat for background/cron tasks
- Launch Flower (Celery dashboard) on port `5555`

---

## 💾 Database Setup & Seeding

After the containers are healthy and running, initialize your schema and load the category hierarchy:

### Apply Database Migrations (Alembic)

```bash
make migrate
```
*Or directly:*
```bash
docker compose -f docker-compose.dev.yml exec fastapi alembic upgrade head
```

### Seed Standard Job Categories

ProConnect uses a semantic matching algorithm between customer descriptions and tradie registered services. Seed the standard Australian home service categories:

```bash
make seed
```
*Or directly:*
```bash
docker compose -f docker-compose.dev.yml exec fastapi python -m seeds.seed_categories
```

---

## 🧪 Verification & Development

### 1. Access the Interfaces
- **Frontend App:** [http://localhost:3000](http://localhost:3000)
- **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Celery Flower Dashboard:** [http://localhost:5555](http://localhost:5555)

### 2. Running the Test Suite
We maintain a robust backend test suite with 100% integration test coverage for core business routes:

```bash
make test
```
*Or directly:*
```bash
docker compose -f docker-compose.dev.yml exec fastapi pytest
```

### 3. Code Quality & Format Checking
We enforce strict Ruff linting, Mypy static analysis, and ESLint rules:

```bash
make lint
```

To automatically format the backend code to match our styling guide:
```bash
make format
```

---

## 🔍 Troubleshooting

### Container Name Conflicts
If you have other postgres or redis containers running locally, make sure to stop them before launching ProConnect:
```bash
docker stop $(docker ps -a -q)
```

### Database Out-of-Sync Errors
If you need to reset your local database fully:
```bash
make clean-docker
make dev
make migrate
make seed
```
