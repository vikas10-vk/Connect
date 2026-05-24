# ProConnect — Australian On-Demand Trades Marketplace 🔧

[![Build Status](https://github.com/vikas10-vk/Connect/actions/workflows/test.yml/badge.svg)](https://github.com/vikas10-vk/Connect/actions/workflows/test.yml)
[![Deployment Status](https://github.com/vikas10-vk/Connect/actions/workflows/deploy.yml/badge.svg)](https://github.com/vikas10-vk/Connect/actions/workflows/deploy.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-cyan.svg)](https://www.docker.com/)

ProConnect is a high-performance, enterprise-grade marketplace platform matching homeowners with licensed trade professionals across Australia. Built to handle extreme concurrency, the system orchestrates real-time geospatial matches, secure online escrow, automated multi-channel notifications, and real-time status updates.

---

## 🌟 Architectural Features

* **Multi-Stage Containerization:** Both Next.js (standalone) and FastAPI backends are containerized with strict non-root policies and minimized sizes (~80MB runtime footprints).
* **Automated Semantic Lead Dispatch:** Advanced NLP algorithms process customer descriptions on the fly, auto-mapping them to standard trade licensing categories for instant notifications.
* **Resilient Distributed Workloads:** Redis-backed Celery worker queues coordinate background processes, email dispatchers, and automated lead escalations.
* **Fully Audited Security Architecture:** Enforces robust role boundaries (RBAC), end-to-end IDOR verification on ownership hierarchies, and secure JWT-based auth flows.
* **Enterprise CI/CD Pipelines:** Complete GitHub Actions integration running linting, strict static analysis, complete test suites, Docker image compilation, and automated SSH-based cluster deployment.

---

## 📦 Tech Stack

| Component | Technology | Role |
|---|---|---|
| **Frontend** | Next.js 14, React, TailwindCSS, TypeScript | Customer & Tradie Portal UI |
| **Backend** | FastAPI, SQLAlchemy (unified asyncio), Alembic | Unified API Webserver |
| **Database** | PostgreSQL 16 | Primary ACID Relational Store |
| **Broker / Cache** | Redis 7 | Background Broker & Performance Cache |
| **Tasks Engine** | Celery 5 | Distributed Workloads & Cron Schedules |
| **Web Proxy** | Nginx | Reverse Proxy & Rate Limiter |
| **Observability** | Sentry, Flower | System Metrics & Error Interceptors |

---

## 📂 Project Anatomy

```
proconnect/                          ← Active repository root
├── .github/
│   ├── workflows/
│   │   ├── test.yml                 ← Standard CI suite (lint + tests)
│   │   └── deploy.yml               ← CD production pipeline
│   └── PULL_REQUEST_TEMPLATE.md     ← Quality checklist for submissions
├── ProConnect/                         ← Core codebase
│   ├── backend/                     ← High-performance FastAPI backend
│   ├── frontend/                    ← Premium standalone Next.js application
│   ├── nginx/                       ← Nginx config and reverse proxy layer
│   ├── docs/                        ← ARCHITECTURAL & DEPLOYMENT MANUALS
│   │   ├── ARCHITECTURE.md          ← Complete systems diagram & flows
│   │   ├── DEPLOYMENT.md            ← SSH, GHCR, and cloud guides
│   │   └── LOCAL_SETUP.md           ← Quick onboarding & local setup
│   ├── docker-compose.dev.yml       ← Full-stack dockerized local stack
│   ├── docker-compose.prod.yml      ← Secure production environment stack
│   ├── Makefile                     ← Comprehensive CLI shortcut controller
│   └── README.md                    ← Hipages workspace reference
└── README.md                        ← Main Repository Guide
```

---

## 🚀 Getting Started

The fastest way to experience ProConnect locally is to spin up our fully dockerized stack. 

### Quick Onboarding

1. **Enter directory:**
   ```bash
   cd ProConnect/
   ```

2. **Clone Configuration Templates:**
   ```bash
   cp .env.example .env
   cp .env.dev.example .env.dev
   ```

3. **Launch the Containers:**
   ```bash
   make dev
   ```

4. **Initialize DB & Categories:**
   ```bash
   make migrate
   make seed
   ```

You are ready! Open [http://localhost:3000](http://localhost:3000) to access the customer interface.

---

## 📖 In-Depth System Manuals

To continue configuring, operating, or developing the platform, consult our comprehensive documentation:

* 📚 **[Local Developer Onboarding & API Guide](file:///c:/Users/Capstone/Intership_main/ProConnect/docs/LOCAL_SETUP.md)**
* 🗺️ **[System Architecture & Core Patterns](file:///c:/Users/Capstone/Intership_main/ProConnect/docs/ARCHITECTURE.md)**
* ⚙️ **[Production Provisioning & Deployment Blueprint](file:///c:/Users/Capstone/Intership_main/ProConnect/docs/DEPLOYMENT.md)**

---

## 🛡️ License

This project is distributed under the MIT License. See [SECURITY.md](file:///c:/Users/Capstone/Intership_main/SECURITY.md) for vulnerability disclosure procedures.
