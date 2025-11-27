# database.py
import sqlite3
import datetime

def init_db():
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    
    # Create table with geolocation support
    c.execute('''CREATE TABLE IF NOT EXISTS reports
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  phone TEXT, 
                  issue_type TEXT,
                  description TEXT,
                  location TEXT,
                  latitude REAL,
                  longitude REAL,
                  image_url TEXT,
                  department TEXT,
                  status TEXT DEFAULT 'received',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Ensure columns exist (for existing databases)
    columns_to_add = [
        'latitude REAL', 'longitude REAL', 'department TEXT'
    ]
    
    for column_def in columns_to_add:
        try:
            column_name = column_def.split()[0]
            c.execute(f"ALTER TABLE reports ADD COLUMN {column_def}")
            print(f"✅ Added column: {column_name}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    conn.commit()
    conn.close()
    print("✅ Database initialized with full geolocation support!")

def save_report(phone, issue_type, description, location, image_url=None, lat=None, lng=None, department=None):
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    
    c.execute("""INSERT INTO reports 
                 (phone, issue_type, description, location, image_url, latitude, longitude, department) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (phone, issue_type, description, location, image_url, lat, lng, department))
    
    conn.commit()
    report_id = c.lastrowid
    conn.close()
    
    print(f"✅ Report #{report_id} saved: {issue_type} at {location} ({lat}, {lng})")
    return report_id

def get_all_reports_with_geodata():
    """Get all reports with geographic data for mapping"""
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    
    c.execute("""
        SELECT id, issue_type, description, location, latitude, longitude, 
               image_url, department, status, created_at
        FROM reports 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY created_at DESC
    """)
    
    reports = c.fetchall()
    conn.close()
    return reports

def get_reports_geojson():
    """Get reports in GeoJSON format for mapping"""
    reports = get_all_reports_with_geodata()
    
    features = []
    for report in reports:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [report[5], report[4]]  # [lng, lat]
            },
            "properties": {
                "id": report[0],
                "issue_type": report[1],
                "description": report[2],
                "location": report[3],
                "image_url": report[6],
                "department": report[7],
                "status": report[8],
                "created_at": report[9],
                "has_image": bool(report[6])
            }
        }
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }