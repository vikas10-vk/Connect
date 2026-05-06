# Contributing to ProConnect

Thank you for contributing! Please read the following before opening a PR.

## Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/vikas10-vk/Connect.git
cd Connect/hipages

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your local values

# 3. Start infrastructure
docker-compose up -d   # PostgreSQL + Redis

# 4. Backend
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000

# 5. Frontend
cd ../frontend
npm install
npm run dev
```

## Branching Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code |
| `dev` | Integration branch — PRs merge here first |
| `feat/<name>` | Feature branches |
| `fix/<name>` | Bug-fix branches |
| `chore/<name>` | Maintenance / refactor |

## Pull Request Checklist

- [ ] Branch is up-to-date with `dev`
- [ ] No `.env` or secret files are staged (`git status`)
- [ ] Code is linted (`ruff check .` / `npm run lint`)
- [ ] Tests pass (if applicable)
- [ ] PR description explains **what** and **why**

## Commit Message Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add tradie profile photo upload
fix: resolve OTP resend rate-limit bug
chore: update dependencies
docs: expand README setup section
```

## Code Style

- **Python**: `ruff` formatter + linter, type hints encouraged
- **TypeScript/React**: ESLint + Prettier (`.eslintrc` / `prettier.config`)
- Keep components small and single-responsibility

## ⚠️ Security Reminder

Never commit API keys, passwords, or tokens. See [SECURITY.md](./SECURITY.md).
