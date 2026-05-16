# ProConnect 🔧

A marketplace connecting homeowners with verified tradies — built with FastAPI, Next.js, PostgreSQL, and Redis.

---

## Prerequisites

Make sure the following are installed on your machine before you begin:

| Tool | Version | Download |
|------|---------|----------|
| **Python** | 3.11+ | https://www.python.org/downloads/ |
| **Node.js** | 18+ | https://nodejs.org/ |
| **Docker Desktop** | Latest | https://www.docker.com/products/docker-desktop/ |
| **Git** | Latest | https://git-scm.com/ |

---

## 🐳 The Easiest Way: Full Docker Setup (Recommended)

If you have Docker installed, you can run the **entire stack** (Frontend, Backend, Database, Redis, Celery) inside containers with a single command! This is the simplest way to get up and running without installing Python or Node.js locally.

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd Intership_main/hipages
   ```

2. **Configure Environment Variables:**
   ```bash
   # Windows
   copy .env.example .env
   # Mac/Linux
   cp .env.example .env
   ```
   *You can leave all values in `.env` as default for local development.*

3. **Start the Entire Application:**
   ```bash
   docker compose -f docker-compose.dev.yml up --build -d
   ```

4. **Run Database Migrations (First time only):**
   ```bash
   docker compose -f docker-compose.dev.yml exec fastapi alembic upgrade head
   ```

That's it! The services will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Flower (Task Monitor)**: http://localhost:5555
- **Mailpit (Local Emails)**: http://localhost:8025

To stop everything, run: `docker compose -f docker-compose.dev.yml down`

---

## 🚀 Windows Quick Start (Alternative)

If you are on Windows and prefer running the code locally on your machine rather than in full Docker containers, use the included `.bat` scripts.

1. **Configure `.env`**: Copy `.env.example` to `.env` as shown above.
2. **Run the Setup Script**:
   Double-click `setup.bat` or run:
   ```cmd
   setup.bat
   ```
   > This automatically sets up the Python virtual environment, installs Python/Node dependencies, starts Docker (for DB+Redis only), and runs migrations!
3. **Start the Application**:
   Double-click `start.bat` or run:
   ```cmd
   start.bat
   ```
   > Opens 3 terminal windows (Backend, Celery, Frontend) and launches your browser.

When done, run `stop.bat` to shut everything down.

---

## 🛠️ Manual Setup Guide (Mac / Linux / Windows)

If you prefer to run things completely manually:

### Step 1 — Configure Environment Variables

```bash
# Copy backend env
cp .env.example .env

# Create frontend env
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > frontend/.env.local
```

### Step 2 — Start Docker (Database + Redis Only)

```bash
docker-compose up -d
```
Starts PostgreSQL on port `5433` and Redis on port `6379`.

### Step 3 — Set Up the Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate      # Mac/Linux
# venv\Scripts\activate       # Windows

# Install dependencies and migrate
pip install -r requirements.txt
alembic upgrade head

# Start backend server
uvicorn main:app --reload --port 8000
```

### Step 4 — Start the Celery Worker (new terminal)

```bash
cd backend
source venv/bin/activate      # Mac/Linux
# venv\Scripts\activate       # Windows

celery -A workers.celery_app worker --loglevel=info --pool=solo
```

### Step 5 — Start the Frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

---

## 📁 Project Structure

```
hipages/
├── backend/                  # FastAPI Python backend
│   ├── routers/              # API route handlers
│   ├── models/               # SQLAlchemy database models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Business logic & integrations
│   ├── workers/              # Celery background tasks
│   ├── alembic/              # Database migrations
│   └── main.py               # App entry point
│
├── frontend/                 # Next.js React frontend
│   ├── src/app/              # Pages (App Router)
│   ├── src/components/       # Reusable UI components
│   ├── src/lib/              # Auth context, API client, utils
│   └── src/hooks/            # Custom React hooks
│
├── .env.example              # Environment variable template
├── docker-compose.dev.yml    # FULL DOCKER stack (Frontend, Backend, DB, Redis, Celery)
├── docker-compose.yml        # DB + Redis ONLY containers
├── setup.bat                 # First-time local setup (Windows)
├── start.bat                 # Launch local services (Windows)
└── stop.bat                  # Stop local services (Windows)
```

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| Docker not starting | Open Docker Desktop first, wait for it to fully load |
| Port 3000 in use | `npx kill-port 3000` |
| Port 8000 in use | `npx kill-port 8000` |
| `venv` not found | Run `python -m venv venv` in the `backend/` folder |
| DB migration error | Ensure Docker is running, then re-run `alembic upgrade head` |
| `npm install` fails | Delete `node_modules/` and run `npm install` again |
| Backend can't connect to DB | Check that `docker-compose up -d` ran successfully |
