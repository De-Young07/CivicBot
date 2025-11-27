# database_migrator.py
import sqlite3
import os

class DatabaseMigrator:
    def __init__(self, db_path='civicbot.db'):
        self.db_path = db_path
    
    def check_column_exists(self, table_name, column_name):
        """Check if a column exists in a table"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute(f"PRAGMA table_info({table_name})")
            columns = [column[1] for column in c.fetchall()]
            return column_name in columns
        finally:
            conn.close()
    
    def migrate_database(self):
        """Apply all necessary database migrations"""
        print("🔄 Starting database migration...")
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Migration 1: Add department column if it doesn't exist
            if not self.check_column_exists('reports', 'department'):
                print("📋 Adding 'department' column to reports table...")
                c.execute("ALTER TABLE reports ADD COLUMN department TEXT")
            
            # Migration 2: Add priority column if it doesn't exist
            if not self.check_column_exists('reports', 'priority'):
                print("📋 Adding 'priority' column to reports table...")
                c.execute("ALTER TABLE reports ADD COLUMN priority TEXT DEFAULT 'medium'")
            
            # Migration 3: Add assigned_to column if it doesn't exist
            if not self.check_column_exists('reports', 'assigned_to'):
                print("📋 Adding 'assigned_to' column to reports table...")
                c.execute("ALTER TABLE reports ADD COLUMN assigned_to TEXT")
            
            # Migration 4: Add resolution_notes column if it doesn't exist
            if not self.check_column_exists('reports', 'resolution_notes'):
                print("📋 Adding 'resolution_notes' column to reports table...")
                c.execute("ALTER TABLE reports ADD COLUMN resolution_notes TEXT")
            
            # Migration 5: Add updated_at column if it doesn't exist
            if not self.check_column_exists('reports', 'updated_at'):
                print("📋 Adding 'updated_at' column to reports table...")
                c.execute("ALTER TABLE reports ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            
            # Migration 6: Add resolved_at column if it doesn't exist
            if not self.check_column_exists('reports', 'resolved_at'):
                print("📋 Adding 'resolved_at' column to reports table...")
                c.execute("ALTER TABLE reports ADD COLUMN resolved_at TIMESTAMP")
            
            # Migration 7: Create departments table if it doesn't exist
            c.execute('''
                CREATE TABLE IF NOT EXISTS departments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    email TEXT,
                    phone TEXT,
                    manager TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Migration 8: Create analytics table if it doesn't exist
            c.execute('''
                CREATE TABLE IF NOT EXISTS analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    recorded_date DATE DEFAULT CURRENT_DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Migration 9: Insert default departments
            default_departments = [
                ('public_works', 'publicworks@city.gov', '+1234567890', 'John Smith'),
                ('sanitation', 'sanitation@city.gov', '+1234567891', 'Maria Garcia'),
                ('water_department', 'water@city.gov', '+1234567892', 'Robert Johnson'),
                ('police', 'police@city.gov', '+1234567893', 'Sarah Wilson'),
                ('parks_department', 'parks@city.gov', '+1234567894', 'Michael Brown'),
                ('traffic_department', 'traffic@city.gov', '+1234567895', 'Lisa Davis')
            ]
            
            for dept in default_departments:
                c.execute('''
                    INSERT OR IGNORE INTO departments (name, email, phone, manager) 
                    VALUES (?, ?, ?, ?)
                ''', dept)
            
            # Migration 10: Create indexes for better performance
            indexes = [
                'CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)',
                'CREATE INDEX IF NOT EXISTS idx_reports_issue_type ON reports(issue_type)',
                'CREATE INDEX IF NOT EXISTS idx_reports_department ON reports(department)',
                'CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at)',
                'CREATE INDEX IF NOT EXISTS idx_reports_location ON reports(location)',
                'CREATE INDEX IF NOT EXISTS idx_reports_priority ON reports(priority)'
            ]
            
            for index_sql in indexes:
                try:
                    c.execute(index_sql)
                except sqlite3.OperationalError as e:
                    print(f"⚠️ Index creation warning: {e}")
            
            conn.commit()
            print("✅ Database migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Database migration failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_database_schema(self):
        """Get current database schema for debugging"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        schema = {}
        
        # Get table info
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in c.fetchall()]
        
        for table in tables:
            c.execute(f"PRAGMA table_info({table})")
            schema[table] = [{'name': row[1], 'type': row[2]} for row in c.fetchall()]
        
        conn.close()
        return schema

# Global instance
migrator = DatabaseMigrator()