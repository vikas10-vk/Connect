"""
create_admin.py — Admin-user management CLI for the Tradie Platform.

Talks directly to the database — bypasses the API and signup flow entirely.
Requires PostgreSQL to be running (docker compose up -d db).

Usage
-----
  python create_admin.py create  --email admin@example.com --name "Admin Name"
  python create_admin.py promote --email existing@example.com
  python create_admin.py demote  --email admin@example.com --to homeowner
  python create_admin.py list
"""

import argparse
import getpass
import sys
import uuid
from datetime import datetime
from pathlib import Path

# ── Load .env ──────────────────────────────────────────────────────────────────
from dotenv import load_dotenv

for candidate in [Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"]:
    if candidate.exists():
        load_dotenv(dotenv_path=candidate, override=True)
        break

import os
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor

# ── DB connection (sync — no async needed for a CLI tool) ─────────────────────
DB_URL = os.getenv("SYNC_DATABASE_URL") or os.getenv("DATABASE_URL", "").replace(
    "postgresql+asyncpg://", "postgresql://"
)

if not DB_URL:
    print("ERROR: No DATABASE_URL found in .env", file=sys.stderr)
    sys.exit(1)


def get_conn():
    try:
        return psycopg2.connect(DB_URL)
    except psycopg2.OperationalError as e:
        print(f"\n✗ Cannot connect to database: {e}", file=sys.stderr)
        print("  Make sure PostgreSQL is running:  docker compose up -d db", file=sys.stderr)
        sys.exit(1)


# ── Helpers ────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def prompt_password() -> str:
    while True:
        pw = getpass.getpass("  Password: ")
        if len(pw) < 8:
            print("  ✗ Must be at least 8 characters. Try again.")
            continue
        pw2 = getpass.getpass("  Confirm:  ")
        if pw != pw2:
            print("  ✗ Passwords do not match. Try again.")
            continue
        return pw


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_create(email: str, name: str):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, role FROM users WHERE email = %s", (email.lower(),))
            existing = cur.fetchone()
            if existing:
                print(f"\n✗ User '{email}' already exists (role: {existing['role']}).")
                print("  Use 'promote' to make them an admin.")
                sys.exit(1)

            print(f"\nCreating admin: {email}")
            password = prompt_password()
            hashed   = hash_password(password)
            user_id  = str(uuid.uuid4())
            now      = datetime.utcnow()

            cur.execute("""
                INSERT INTO users
                    (id, email, full_name, hashed_password, role,
                     is_active, is_verified, email_verified, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'admin', true, true, true, %s, %s)
            """, (user_id, email.lower().strip(), name.strip(), hashed, now, now))
            conn.commit()

        print(f"\n✓ Admin created.")
        print(f"  Email : {email.lower().strip()}")
        print(f"  Name  : {name.strip()}")
        print(f"  ID    : {user_id}")
        print(f"\n  Log in at /login with these credentials.\n")
    finally:
        conn.close()


def cmd_promote(email: str):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, email, full_name, role FROM users WHERE email = %s", (email.lower(),))
            user = cur.fetchone()
            if not user:
                print(f"\n✗ No user found with email '{email}'.")
                sys.exit(1)
            if user["role"] == "admin":
                print(f"\n✓ '{email}' is already an admin. Nothing changed.")
                sys.exit(0)

            print(f"\nPromoting to admin:")
            print(f"  Name : {user['full_name']}")
            print(f"  From : {user['role']}  →  admin")
            if input("\n  Confirm? [y/N]: ").strip().lower() != "y":
                print("  Aborted.")
                sys.exit(0)

            cur.execute(
                "UPDATE users SET role = 'admin', updated_at = %s WHERE email = %s",
                (datetime.utcnow(), email.lower()),
            )
            conn.commit()
        print(f"\n✓ '{email}' is now admin.\n")
    finally:
        conn.close()


def cmd_demote(email: str, to_role: str):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT full_name, role FROM users WHERE email = %s", (email.lower(),))
            user = cur.fetchone()
            if not user:
                print(f"\n✗ No user found with email '{email}'.")
                sys.exit(1)
            if user["role"] != "admin":
                print(f"\n✗ '{email}' is not an admin (role: {user['role']}).")
                sys.exit(0)

            print(f"\nDemoting admin:")
            print(f"  Name : {user['full_name']}")
            print(f"  From : admin  →  {to_role}")
            if input("\n  Confirm? [y/N]: ").strip().lower() != "y":
                print("  Aborted.")
                sys.exit(0)

            cur.execute(
                "UPDATE users SET role = %s, updated_at = %s WHERE email = %s",
                (to_role, datetime.utcnow(), email.lower()),
            )
            conn.commit()
        print(f"\n✓ '{email}' demoted to '{to_role}'.\n")
    finally:
        conn.close()


def cmd_list():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT email, full_name, is_active, created_at FROM users "
                "WHERE role = 'admin' ORDER BY created_at ASC"
            )
            admins = cur.fetchall()

        if not admins:
            print("\nNo admin users found.\n")
            return

        print(f"\n{'─' * 65}")
        print(f"  {'EMAIL':<30}  {'NAME':<20}  ACTIVE")
        print(f"{'─' * 65}")
        for a in admins:
            print(f"  {a['email']:<30}  {a['full_name']:<20}  {'yes' if a['is_active'] else 'no'}")
        print(f"{'─' * 65}")
        print(f"  {len(admins)} admin(s)\n")
    finally:
        conn.close()


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Admin user CLI — Tradie Platform")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create",  help="Create a new admin user")
    p.add_argument("--email", required=True)
    p.add_argument("--name",  required=True)

    p = sub.add_parser("promote", help="Promote existing user to admin")
    p.add_argument("--email", required=True)

    p = sub.add_parser("demote",  help="Demote admin to regular role")
    p.add_argument("--email", required=True)
    p.add_argument("--to", dest="to_role", default="homeowner", choices=["homeowner", "tradie"])

    sub.add_parser("list", help="List all admins")

    args = parser.parse_args()
    try:
        if args.command == "create":  cmd_create(args.email, args.name)
        elif args.command == "promote": cmd_promote(args.email)
        elif args.command == "demote":  cmd_demote(args.email, args.to_role)
        elif args.command == "list":    cmd_list()
    except KeyboardInterrupt:
        print("\n\nAborted.")


if __name__ == "__main__":
    main()
