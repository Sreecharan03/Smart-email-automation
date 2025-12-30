
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'email-assistant')))

from config import get_config, get_supabase_connection_params
import psycopg2

def check_accounts():
    try:
        config = get_config()
        params = get_supabase_connection_params(config)
        
        with psycopg2.connect(**params) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM email_accounts")
                count = cur.fetchone()[0]
                print(f"Total accounts in DB: {count}")
                
                if count > 0:
                    cur.execute("SELECT id, email_address FROM email_accounts")
                    rows = cur.fetchall()
                    for row in rows:
                        print(f"ID: {row[0]}, Email: {row[1]}")
                else:
                    print("No accounts found.")
                    
    except Exception as e:
        print(f"Error checking DB: {e}")

if __name__ == "__main__":
    check_accounts()
