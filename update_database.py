# update_database.py
import sqlite3
import os

def update_database_schema():
    """Add latitude and longitude columns to the reports table"""
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    
    try:
        c.execute("PRAGMA table_info(reports)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'latitude' not in columns:
            print("Adding latitude and longitude columns to reports table...")
            c.execute("ALTER TABLE reports ADD COLUMN latitude REAL")
            c.execute("ALTER TABLE reports ADD COLUMN longitude REAL")
            conn.commit()
            print("✅ Database schema updated successfully!")
        else:
            print("✅ Database schema is already up to date")
            
    except Exception as e:
        print(f"Error updating database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_database_schema()
