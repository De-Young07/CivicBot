import sqlite3
import datetime

def init_db():
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  phone TEXT, 
                  issue_type TEXT,
                  description TEXT,
                  location TEXT,
                  image_url TEXT,
                  status TEXT DEFAULT 'received',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("✅ Database initialized!")

def save_report(phone, issue_type, description, location, image_url=None):
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    c.execute("INSERT INTO reports (phone, issue_type, description, location, image_url) VALUES (?, ?, ?, ?, ?)",
              (phone, issue_type, description, location, image_url))
    conn.commit()
    report_id = c.lastrowid
    conn.close()
    print(f"✅ Report saved with ID: {report_id}, Image: {image_url is not None}")
    return report_id

def get_report_status(report_id):
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    c.execute("SELECT status, issue_type FROM reports WHERE id = ?", (report_id,))
    result = c.fetchone()
    conn.close()
    return result

def notify_user(phone, report_id, new_status):
    """This would integrate with Twilio to send status updates"""
    status_messages = {
        'in-progress': f"🔄 Good news! Your report #{report_id} is now being worked on.",
        'resolved': f"✅ Great news! Your report #{report_id} has been resolved. Thank you for helping improve our community!"
    }
    
    if new_status in status_messages:
        # In a real implementation, you'd send this via Twilio
        print(f"📤 Would notify {phone}: {status_messages[new_status]}")
        return True
    return False