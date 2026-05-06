"""
Alembic migration — Generative UI additions
Run with: alembic revision --autogenerate -m "generative_ui"
         alembic upgrade head

OR apply the raw SQL below manually using psql or pgAdmin.
"""

# ── Raw SQL (apply manually if Alembic autogenerate misses anything) ─────────

MIGRATION_SQL = """
-- 1. Add Generative UI columns to chat_conversations
ALTER TABLE chat_conversations
    ADD COLUMN IF NOT EXISTS ui_component  TEXT        DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS image_url     VARCHAR(500) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS insight_tags  TEXT        DEFAULT NULL;

-- 2. Create user_insights table for persistent memory
CREATE TABLE IF NOT EXISTS user_insights (
    id                  VARCHAR         PRIMARY KEY,
    user_id             VARCHAR         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    home_suburb         VARCHAR(100)    DEFAULT NULL,
    home_state          VARCHAR(10)     DEFAULT NULL,
    home_postcode       VARCHAR(10)     DEFAULT NULL,
    mentioned_problems  TEXT            DEFAULT '[]',
    mentioned_assets    TEXT            DEFAULT '[]',
    trade_interests     TEXT            DEFAULT '[]',
    unresolved_issues   TEXT            DEFAULT '[]',
    key_tags            TEXT            DEFAULT '[]',
    user_intent         VARCHAR(50)     DEFAULT NULL,
    last_sentiment      VARCHAR(20)     DEFAULT NULL,
    created_at          TIMESTAMP       DEFAULT NOW(),
    updated_at          TIMESTAMP       DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_insights_user_id ON user_insights(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_session ON chat_conversations(session_id);
"""

print("Copy the SQL above and run it against your PostgreSQL database.")
print("Then run: alembic stamp head")