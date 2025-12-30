
import psycopg2
import sys
import os

# Add the project root to the python path so we can import from email-assistant
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), 'email-assistant')))

from config import get_supabase_connection_params, get_config

def show_emails():
    try:
        config = get_config()
        db_params = get_supabase_connection_params(config)

        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cur:
                # Show real email subjects and senders
                cur.execute('''
                    SELECT subject, sender_email, date_sent, external_message_id
                    FROM email_messages
                    ORDER BY date_sent DESC
                    LIMIT 5
                ''')

                print('🔍 REAL EMAILS IN DATABASE:')
                rows = cur.fetchall()
                if not rows:
                    print("No emails found in the database.")
                
                for row in rows:
                    print(f'📧 Subject: {row[0][:50]}...' if row[0] else '📧 Subject: (No Subject)')
                    print(f'   From: {row[1]}')
                    print(f'   Date: {row[2]}')
                    print(f'   Gmail ID: {row[3]}')
                    print('---')
    except Exception as e:
        print(f"Error fetching emails: {e}")

if __name__ == "__main__":
    show_emails()
