# test_db_connection.py
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

# --- Make sure we can import config.py from email-assistant ---
PROJECT_ROOT = Path(__file__).resolve().parent
EMAIL_ASSISTANT_DIR = PROJECT_ROOT / "email-assistant"

sys.path.insert(0, str(EMAIL_ASSISTANT_DIR))

from config import get_config, get_supabase_connection_params  # type: ignore


def main():
    print("🚀 Testing Supabase DB connection via .env + config.py\n")

    # 1) Load config (this also loads .env inside config.py)
    config = get_config()

    print("📦 Loaded DB config from .env:")
    print(f"  DB_HOST = {config.db_host}")
    print(f"  DB_PORT = {config.db_port}")
    print(f"  DB_NAME = {config.db_name}")
    print(f"  DB_USER = {config.db_user}")
    # don't print password for safety

    # 2) Build psycopg2 connection params
    conn_params = get_supabase_connection_params(config)
    safe_params = {k: v for k, v in conn_params.items() if k != "password"}

    print("\n🔧 psycopg2 connection params (safe):")
    for k, v in safe_params.items():
        print(f"  {k}: {v}")

    # 3) Try to connect and run a simple query
    try:
        print("\n🔌 Connecting to database...")
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()

        cur.execute("SELECT current_database(), current_user, NOW();")
        db_name, db_user, now = cur.fetchone()

        print("\n✅ Connection successful!")
        print(f"  current_database = {db_name}")
        print(f"  current_user     = {db_user}")
        print(f"  server_time      = {now}")

        cur.close()
        conn.close()
        print("\n🎉 Supabase DB is reachable and .env is loading correctly.")

    except Exception as e:
        print("\n❌ Connection FAILED")
        print(f"   Error: {e}")


if __name__ == "__main__":
    main()
