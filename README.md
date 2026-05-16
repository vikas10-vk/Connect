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

## 🚀 The Easiest Way: Windows Quick Start

If you are on Windows, you can use the included `.bat` scripts instead of running each step manually. This is the **recommended** way for team members to get started quickly.

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd Intership_main/hipages
   ```

2. **Run the Setup Script:**
   Double-click `setup.bat` in the `hipages` folder, or run it from the terminal:
   ```cmd
   setup.bat
   ```
   > This will automatically create the Python virtual environment, install all Python and Node.js dependencies, start Docker, and run the database migrations!

3. **Configure Environment Variables:**
   Copy `.env.example` to `.env` in the `hipages` folder:
   ```cmd
   copy .env.example .env
   ```
   Then follow the [Environment Variables Guide](#-configure-environment-variables) below to fill in your `SECRET_KEY`.

4. **Start the Application:**
   Double-click `start.bat` or run:
   ```cmd
   start.bat
   ```
   > This script will automatically open 3 terminal windows (Backend, Celery, and Frontend) and launch the application in your browser.

When you're done working, just run `stop.bat` to shut everything down.

---

## 🛠️ Manual Setup Guide (Mac / Linux / Windows)

If you are not on Windows or prefer to run things manually, follow these steps.

### Step 1 — Clone the Repository

```bash
git clone <repository_url>
cd Intership_main/hipages
```

---

### Step 2 — Configure Environment Variables

Copy the example env file and fill in your values in the `hipages` directory:

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Also create the frontend env file:

```bash
# Windows
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > frontend\.env.local

# Mac / Linux
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > frontend/.env.local
```

> ⚠️ **Never commit `.env` or `.env.local` files.** They are already listed in `.gitignore`.

#### 🔑 How to Generate Your `SECRET_KEY`

`SECRET_KEY` is a random string used to sign JWT tokens. **You create it yourself** — it is not from any external service. Open `.env` and fill in the values.

Run **one** of these commands to generate a secure key and copy the output into your `.env`:

```bash
# Option 1 — Python (works on Windows, Mac, Linux)
python -c "import secrets; print(secrets.token_hex(32))"

# Option 2 — PowerShell (Windows)
[System.Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))

# Option 3 — Mac / Linux terminal
openssl rand -hex 32
```

Paste the output as the value of `SECRET_KEY` in your `.env` file. Example:
```env
SECRET_KEY=3f8a2c1e9b7d4f6a0e5c2b8d1a3f7e9c4b6d2a8f1e5c3b7d9a2f4e6c1b8d3a7
```

> ✅ You can leave all `OPTIONAL` fields in the `.env` blank for basic local development. The app will still run.

---

### Step 3 — Start Docker (Database + Redis)

Make sure Docker Desktop is open and running, then:

```bash
docker-compose up -d
```

This starts **PostgreSQL** on port `5433` and **Redis** on port `6379`.

---

### Step 4 — Set Up the Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the backend server
uvicorn main:app --reload --port 8000
```

---

### Step 5 — Start the Celery Worker (new terminal)

```bash
cd backend
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac / Linux

celery -A workers.celery_app worker --loglevel=info --pool=solo
```

---

### Step 6 — Set Up and Start the Frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

---

### ✅ Services Running

| Service | URL |
|---------|-----|
| Frontend (Next.js) | http://localhost:3000 |
| Backend (FastAPI) | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

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
├── docker-compose.yml        # PostgreSQL + Redis containers
├── setup.bat                 # First-time setup (Windows)
├── start.bat                 # Launch all services (Windows)
└── stop.bat                  # Stop all services (Windows)
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
