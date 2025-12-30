# ====================================
# UNIFIED AI EMAIL ASSISTANT - SUPABASE DATABASE SETUP
# ====================================
# Creates all necessary database tables in Supabase PostgreSQL
# Handles table creation, indexes, and constraints for optimal performance

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from config import get_config, get_supabase_connection_params, is_supabase_configured
import uuid
from datetime import datetime
import sys

def get_create_table_sql():
    """
    Returns list of SQL statements to create all tables
    Based on the database models defined in database_models.py
    """
    
    create_tables = [
        # ====================================
        # EMAIL ACCOUNTS TABLE
        # ====================================
        """
        CREATE TABLE IF NOT EXISTS email_accounts (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            account_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
            provider VARCHAR(50) NOT NULL,
            email_address VARCHAR(255) NOT NULL,
            display_name VARCHAR(255),
            access_token TEXT,
            refresh_token TEXT NOT NULL,
            token_expiry TIMESTAMPTZ,
            granted_scopes JSONB,
            is_active BOOLEAN DEFAULT TRUE,
            last_sync_at TIMESTAMPTZ,
            sync_cursor VARCHAR(255),
            connected_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT unique_user_email UNIQUE (user_id, email_address)
        );
        """,
        
        # ====================================
        # EMAIL MESSAGES TABLE
        # ====================================
        """
        CREATE TABLE IF NOT EXISTS email_messages (
            id SERIAL PRIMARY KEY,
            message_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
            account_id INTEGER REFERENCES email_accounts(id) ON DELETE CASCADE,
            external_message_id VARCHAR(255) NOT NULL,
            thread_id VARCHAR(255),
            sender_email VARCHAR(255) NOT NULL,
            sender_name VARCHAR(255),
            recipients JSONB,
            cc_recipients JSONB,
            bcc_recipients JSONB,
            subject TEXT,
            snippet TEXT,
            body_plain TEXT,
            body_html TEXT,
            date_sent TIMESTAMPTZ NOT NULL,
            date_received TIMESTAMPTZ,
            is_read BOOLEAN DEFAULT FALSE,
            is_important BOOLEAN DEFAULT FALSE,
            has_attachments BOOLEAN DEFAULT FALSE,
            attachment_count INTEGER DEFAULT 0,
            labels JSONB,
            folder_name VARCHAR(255),
            size_bytes INTEGER,
            message_format VARCHAR(50),
            is_processed BOOLEAN DEFAULT FALSE,
            processing_error TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT unique_account_message UNIQUE (account_id, external_message_id)
        );
        """,
        
        # ====================================
        # MESSAGE EMBEDDINGS TABLE
        # ====================================
        """
        CREATE TABLE IF NOT EXISTS message_embeddings (
            id SERIAL PRIMARY KEY,
            message_id INTEGER REFERENCES email_messages(id) ON DELETE CASCADE,
            field_name VARCHAR(50) NOT NULL,
            embedding_model VARCHAR(100) NOT NULL,
            vector_id VARCHAR(255) NOT NULL,
            qdrant_collection VARCHAR(100) NOT NULL,
            vector_dimensions INTEGER NOT NULL,
            embedding_version VARCHAR(50) DEFAULT 'v1',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT unique_message_field_embedding UNIQUE (message_id, field_name, embedding_model)
        );
        """,
        
        # ====================================
        # EMAIL DRAFTS TABLE
        # ====================================
        """
        CREATE TABLE IF NOT EXISTS email_drafts (
            id SERIAL PRIMARY KEY,
            draft_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
            account_id INTEGER REFERENCES email_accounts(id) ON DELETE CASCADE,
            original_message_id INTEGER REFERENCES email_messages(id) ON DELETE SET NULL,
            recipient_email VARCHAR(255) NOT NULL,
            subject TEXT NOT NULL,
            body_text TEXT NOT NULL,
            body_html TEXT,
            draft_type VARCHAR(50) NOT NULL,
            tone VARCHAR(50),
            length VARCHAR(50),
            ai_model_used VARCHAR(100),
            generation_prompt TEXT,
            ai_confidence DECIMAL(3,2),
            user_edits JSONB,
            edit_count INTEGER DEFAULT 0,
            approval_status VARCHAR(50) DEFAULT 'pending',
            is_sent BOOLEAN DEFAULT FALSE,
            sent_at TIMESTAMPTZ,
            sent_message_id VARCHAR(255),
            safety_check_passed BOOLEAN DEFAULT FALSE,
            safety_issues JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
        
        # ====================================
        # IMPORTANCE SCORES TABLE
        # ====================================
        """
        CREATE TABLE IF NOT EXISTS importance_scores (
            id SERIAL PRIMARY KEY,
            message_id INTEGER REFERENCES email_messages(id) ON DELETE CASCADE,
            overall_score DECIMAL(4,3) NOT NULL,
            urgency_score DECIMAL(4,3),
            relevance_score DECIMAL(4,3),
            sender_importance DECIMAL(4,3),
            scoring_factors JSONB,
            scoring_reasons TEXT[],
            model_used VARCHAR(100),
            model_version VARCHAR(50),
            calculated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
        
        # ====================================
        # DAILY DIGESTS TABLE
        # ====================================
        """
        CREATE TABLE IF NOT EXISTS daily_digests (
            id SERIAL PRIMARY KEY,
            digest_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
            user_id VARCHAR(255) NOT NULL,
            digest_date TIMESTAMPTZ NOT NULL,
            summary_text TEXT NOT NULL,
            summary_html TEXT,
            total_emails INTEGER DEFAULT 0,
            important_emails INTEGER DEFAULT 0,
            unread_emails INTEGER DEFAULT 0,
            action_items JSONB,
            pending_replies JSONB,
            delivery_method VARCHAR(50),
            is_delivered BOOLEAN DEFAULT FALSE,
            delivered_at TIMESTAMPTZ,
            ai_model_used VARCHAR(100),
            generation_time_seconds DECIMAL(6,3),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT unique_user_digest_date UNIQUE (user_id, digest_date)
        );
        """,
        
        # ====================================
        # SYSTEM LOGS TABLE
        # ====================================
        """
        CREATE TABLE IF NOT EXISTS system_logs (
            id SERIAL PRIMARY KEY,
            log_level VARCHAR(20) NOT NULL,
            event_type VARCHAR(100) NOT NULL,
            message TEXT NOT NULL,
            user_id VARCHAR(255),
            account_id INTEGER,
            session_id VARCHAR(255),
            execution_time_ms DECIMAL(10,3),
            memory_usage_mb DECIMAL(10,3),
            metadata JSONB,
            stack_trace TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    ]
    
    return create_tables

def get_create_indexes_sql():
    """
    Returns list of SQL statements to create indexes for better performance
    """
    
    create_indexes = [
        # Email Accounts Indexes
        "CREATE INDEX IF NOT EXISTS ix_email_accounts_user_provider ON email_accounts (user_id, provider);",
        "CREATE INDEX IF NOT EXISTS ix_email_accounts_email ON email_accounts (email_address);",
        
        # Email Messages Indexes
        "CREATE INDEX IF NOT EXISTS ix_email_messages_account_date ON email_messages (account_id, date_sent);",
        "CREATE INDEX IF NOT EXISTS ix_email_messages_sender ON email_messages (sender_email);",
        "CREATE INDEX IF NOT EXISTS ix_email_messages_thread ON email_messages (thread_id);",
        "CREATE INDEX IF NOT EXISTS ix_email_messages_external_id ON email_messages (external_message_id);",
        "CREATE INDEX IF NOT EXISTS ix_email_messages_processed ON email_messages (is_processed);",
        "CREATE INDEX IF NOT EXISTS ix_email_messages_date_sent ON email_messages (date_sent);",
        
        # Message Embeddings Indexes
        "CREATE INDEX IF NOT EXISTS ix_embeddings_message_field ON message_embeddings (message_id, field_name);",
        "CREATE INDEX IF NOT EXISTS ix_embeddings_vector_id ON message_embeddings (vector_id);",
        
        # Email Drafts Indexes
        "CREATE INDEX IF NOT EXISTS ix_drafts_account_status ON email_drafts (account_id, approval_status);",
        "CREATE INDEX IF NOT EXISTS ix_drafts_created_at ON email_drafts (created_at);",
        
        # Importance Scores Indexes
        "CREATE INDEX IF NOT EXISTS ix_importance_scores_score ON importance_scores (overall_score);",
        "CREATE INDEX IF NOT EXISTS ix_importance_scores_message ON importance_scores (message_id);",
        
        # Daily Digests Indexes
        "CREATE INDEX IF NOT EXISTS ix_daily_digests_user_date ON daily_digests (user_id, digest_date);",
        
        # System Logs Indexes
        "CREATE INDEX IF NOT EXISTS ix_system_logs_level_type ON system_logs (log_level, event_type);",
        "CREATE INDEX IF NOT EXISTS ix_system_logs_created_at ON system_logs (created_at);"
    ]
    
    return create_indexes

def create_updated_at_trigger():
    """
    Creates a trigger function to automatically update 'updated_at' timestamps
    """
    
    trigger_sql = [
        # Create trigger function
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """,
        
        # Apply trigger to tables with updated_at column
        """
        DROP TRIGGER IF EXISTS update_email_accounts_updated_at ON email_accounts;
        CREATE TRIGGER update_email_accounts_updated_at 
            BEFORE UPDATE ON email_accounts 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """,
        
        """
        DROP TRIGGER IF EXISTS update_email_messages_updated_at ON email_messages;
        CREATE TRIGGER update_email_messages_updated_at 
            BEFORE UPDATE ON email_messages 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """,
        
        """
        DROP TRIGGER IF EXISTS update_email_drafts_updated_at ON email_drafts;
        CREATE TRIGGER update_email_drafts_updated_at 
            BEFORE UPDATE ON email_drafts 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    ]
    
    return trigger_sql

def setup_database():
    """
    Main function to set up all database tables, indexes, and triggers
    """
    try:
        # Load configuration
        config = get_config()
        
        if not is_supabase_configured(config):
            print("❌ Supabase database not configured. Check your .env file.")
            return False
        
        # Get connection parameters
        conn_params = get_supabase_connection_params(config)
        
        print("🗄️ Setting up Email Assistant Database...")
        print(f"📍 Connecting to {config.db_host}:{config.db_port}")
        
        # Connect to database
        connection = psycopg2.connect(**conn_params)
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = connection.cursor()
        
        print("✅ Connected to Supabase!")
        
        # Create tables
        print("\n📊 Creating database tables...")
        tables_sql = get_create_table_sql()
        table_names = [
            "email_accounts", "email_messages", "message_embeddings", 
            "email_drafts", "importance_scores", "daily_digests", "system_logs"
        ]
        
        for i, (table_sql, table_name) in enumerate(zip(tables_sql, table_names), 1):
            try:
                cursor.execute(table_sql)
                print(f"  {i}. ✅ Created table: {table_name}")
            except Exception as e:
                print(f"  {i}. ⚠️ Table {table_name}: {e}")
        
        # Create indexes
        print("\n🚀 Creating database indexes...")
        indexes_sql = get_create_indexes_sql()
        
        for i, index_sql in enumerate(indexes_sql, 1):
            try:
                cursor.execute(index_sql)
                if i % 3 == 0:  # Print progress every 3 indexes
                    print(f"  ✅ Created {i}/{len(indexes_sql)} indexes...")
            except Exception as e:
                print(f"  ⚠️ Index {i}: {e}")
        
        print(f"  ✅ Created all {len(indexes_sql)} indexes!")
        
        # Create triggers
        print("\n⚡ Setting up database triggers...")
        trigger_sql = create_updated_at_trigger()
        
        for i, sql in enumerate(trigger_sql, 1):
            try:
                cursor.execute(sql)
                if "FUNCTION" in sql:
                    print(f"  {i}. ✅ Created trigger function")
                else:
                    print(f"  {i}. ✅ Applied trigger to table")
            except Exception as e:
                print(f"  {i}. ⚠️ Trigger: {e}")
        
        # Verify table creation
        print("\n🔍 Verifying database setup...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('email_accounts', 'email_messages', 'message_embeddings', 
                              'email_drafts', 'importance_scores', 'daily_digests', 'system_logs')
            ORDER BY table_name;
        """)
        
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"📋 Database Tables Created: {len(existing_tables)}/7")
        for table in existing_tables:
            print(f"  ✅ {table}")
        
        # Test table insertion
        print("\n🧪 Testing table functionality...")
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        
        # Test email_accounts table
        cursor.execute("""
            INSERT INTO email_accounts (user_id, provider, email_address, refresh_token) 
            VALUES (%s, 'test', 'test@example.com', 'test_token')
            RETURNING id;
        """, (test_user_id,))
        
        test_account_id = cursor.fetchone()[0]
        print(f"  ✅ Test account created with ID: {test_account_id}")
        
        # Clean up test data
        cursor.execute("DELETE FROM email_accounts WHERE user_id = %s;", (test_user_id,))
        print(f"  ✅ Test data cleaned up")
        
        # Close connection
        cursor.close()
        connection.close()
        
        print(f"\n🎉 Database setup completed successfully!")
        print(f"📈 Ready for Phase 2: Email Connection & Data Ingestion")
        
        return True
        
    except ImportError:
        print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def reset_database():
    """
    DANGER: Drops all tables. Use only for development!
    """
    print("⚠️ WARNING: This will delete all data!")
    confirm = input("Type 'RESET' to confirm: ")
    
    if confirm != 'RESET':
        print("❌ Reset cancelled.")
        return False
    
    try:
        config = get_config()
        conn_params = get_supabase_connection_params(config)
        
        connection = psycopg2.connect(**conn_params)
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = connection.cursor()
        
        # Drop tables in reverse order (due to foreign keys)
        tables_to_drop = [
            "system_logs", "daily_digests", "importance_scores", 
            "email_drafts", "message_embeddings", "email_messages", "email_accounts"
        ]
        
        print("🗑️ Dropping tables...")
        for table in tables_to_drop:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                print(f"  ✅ Dropped {table}")
            except Exception as e:
                print(f"  ⚠️ {table}: {e}")
        
        cursor.close()
        connection.close()
        
        print("✅ Database reset complete!")
        return True
        
    except Exception as e:
        print(f"❌ Reset failed: {e}")
        return False

def show_table_info():
    """
    Display information about existing tables
    """
    try:
        config = get_config()
        conn_params = get_supabase_connection_params(config)
        
        connection = psycopg2.connect(**conn_params)
        cursor = connection.cursor()
        
        print("📊 Database Table Information")
        print("=" * 50)
        
        # Get table info
        cursor.execute("""
            SELECT 
                t.table_name,
                (SELECT COUNT(*) FROM information_schema.columns 
                 WHERE table_name = t.table_name AND table_schema = 'public') as column_count
            FROM information_schema.tables t
            WHERE t.table_schema = 'public' 
            AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name;
        """)
        
        tables = cursor.fetchall()
        
        if tables:
            print(f"Total Tables: {len(tables)}")
            for table_name, column_count in tables:
                print(f"  📋 {table_name}: {column_count} columns")
        else:
            print("No tables found. Run setup_database() first.")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"❌ Failed to get table info: {e}")

# ====================================
# MAIN FUNCTION FOR TESTING
# ====================================

def main():
    """Main function with menu for database operations"""
    print("🗄️ Email Assistant Database Setup")
    print("=" * 40)
    print("1. Setup database (create tables)")
    print("2. Show table information") 
    print("3. Reset database (⚠️ DANGER)")
    print("4. Exit")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == "1":
        setup_database()
    elif choice == "2":
        show_table_info()
    elif choice == "3":
        reset_database()
    elif choice == "4":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()