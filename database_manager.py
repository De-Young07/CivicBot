# database_manager.py
import sqlite3
import csv
import json
from datetime import datetime, timedelta
import os
import time

class DatabaseManager:
    def __init__(self, db_path='civicbot.db'):
        self.db_path = db_path
        self._run_migrations()
        self.init_database()
    
    def _run_migrations(self):
        """Run all necessary database migrations"""
        print("🔄 Running database migrations...")
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Check current schema
            c.execute("PRAGMA table_info(reports)")
            existing_columns = [column[1] for column in c.fetchall()]
            print(f"📊 Existing columns: {existing_columns}")
            
            # Define columns to add
            columns_to_add = [
                ('department', 'TEXT'),
                ('priority', 'TEXT DEFAULT "medium"'),
                ('assigned_to', 'TEXT'),
                ('resolution_notes', 'TEXT'),
                ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
                ('resolved_at', 'TIMESTAMP'),
                ('latitude', 'REAL'),
                ('longitude', 'REAL')
            ]
            
            # Add missing columns
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    print(f"📋 Adding '{column_name}' column...")
                    try:
                        c.execute(f"ALTER TABLE reports ADD COLUMN {column_name} {column_type}")
                        print(f"✅ Added '{column_name}' successfully")
                    except Exception as e:
                        print(f"⚠️ Could not add '{column_name}': {e}")
            
            # Create departments table
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
            
            # Create analytics table
            c.execute('''
                CREATE TABLE IF NOT EXISTS analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    recorded_date DATE DEFAULT CURRENT_DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert default departments
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
            
            # Create indexes
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
                except Exception as e:
                    print(f"⚠️ Index creation warning: {e}")
            
            conn.commit()
            print("✅ All migrations completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration error: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize the main database tables"""
        conn = self.get_connection()
        c = conn.cursor()
        
        # Create main reports table with all columns
        c.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                issue_type TEXT NOT NULL,
                description TEXT,
                location TEXT,
                latitude REAL,
                longitude REAL,
                image_url TEXT,
                department TEXT,
                status TEXT DEFAULT 'received',
                priority TEXT DEFAULT 'medium',
                assigned_to TEXT,
                resolution_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialization complete!")
    
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # Basic CRUD Operations
    def create_report(self, report_data):
        """Create a new report"""
        conn = self.get_connection()
        c = conn.cursor()
        
        # Set defaults for required fields
        report_data.setdefault('status', 'received')
        report_data.setdefault('priority', 'medium')
        report_data.setdefault('created_at', datetime.now().isoformat())
        report_data.setdefault('updated_at', datetime.now().isoformat())
        
        columns = []
        placeholders = []
        values = []
        
        for key, value in report_data.items():
            if value is not None:  # Only include non-None values
                columns.append(key)
                placeholders.append('?')
                values.append(value)
        
        query = f'''
            INSERT INTO reports ({', '.join(columns)}) 
            VALUES ({', '.join(placeholders)})
        '''
        
        try:
            c.execute(query, values)
            report_id = c.lastrowid
            conn.commit()
            print(f"✅ Report #{report_id} created successfully")
            return report_id
        except Exception as e:
            print(f"❌ Error creating report: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def get_report(self, report_id):
        """Get a single report by ID"""
        conn = self.get_connection()
        c = conn.cursor()
        
        c.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
        report = c.fetchone()
        conn.close()
        
        return dict(report) if report else None
    
    def get_reports(self, filters=None, page=1, per_page=50, sort_by='created_at', sort_order='DESC'):
        """Get reports with filtering and pagination"""
        conn = self.get_connection()
        c = conn.cursor()
        
        where_conditions = []
        params = []
        
        if filters:
            for key, value in filters.items():
                if value is not None:
                    if key == 'search':
                        where_conditions.append('(description LIKE ? OR location LIKE ?)')
                        params.extend([f'%{value}%', f'%{value}%'])
                    else:
                        where_conditions.append(f'{key} = ?')
                        params.append(value)
        
        where_clause = ' AND '.join(where_conditions) if where_conditions else '1=1'
        offset = (page - 1) * per_page
        
        query = f'''
            SELECT * FROM reports 
            WHERE {where_clause}
            ORDER BY {sort_by} {sort_order}
            LIMIT ? OFFSET ?
        '''
        
        params.extend([per_page, offset])
        
        c.execute(query, params)
        reports = [dict(row) for row in c.fetchall()]
        
        # Get total count for pagination
        count_query = f'SELECT COUNT(*) FROM reports WHERE {where_clause}'
        c.execute(count_query, params[:-2])
        total_count = c.fetchone()[0]
        
        conn.close()
        
        return {
            'reports': reports,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        }
    
    def update_report(self, report_id, update_data):
        """Update a report"""
        conn = self.get_connection()
        c = conn.cursor()
        
        # Always update the updated_at timestamp
        update_data['updated_at'] = datetime.now().isoformat()
        
        set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
        values = list(update_data.values()) + [report_id]
        
        query = f'UPDATE reports SET {set_clause} WHERE id = ?'
        
        try:
            c.execute(query, values)
            conn.commit()
            success = c.rowcount > 0
            if success:
                print(f"✅ Report #{report_id} updated successfully")
            else:
                print(f"⚠️ Report #{report_id} not found for update")
            return success
        except Exception as e:
            print(f"❌ Error updating report: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    # Analytics Methods
    def get_dashboard_stats(self):
        """Get comprehensive dashboard statistics"""
        conn = self.get_connection()
        c = conn.cursor()
        
        stats = {}
        
        try:
            # Basic counts
            c.execute('SELECT COUNT(*) FROM reports')
            stats['total_reports'] = c.fetchone()[0]
            
            c.execute('SELECT COUNT(*) FROM reports WHERE status = "resolved"')
            stats['resolved_reports'] = c.fetchone()[0]
            
            c.execute('SELECT COUNT(*) FROM reports WHERE image_url IS NOT NULL AND image_url != ""')
            stats['reports_with_images'] = c.fetchone()[0]
            
            # Distributions
            c.execute('SELECT status, COUNT(*) FROM reports GROUP BY status')
            stats['status_distribution'] = dict(c.fetchall())
            
            c.execute('SELECT issue_type, COUNT(*) FROM reports GROUP BY issue_type')
            stats['issue_type_distribution'] = dict(c.fetchall())
            
            c.execute('SELECT department, COUNT(*) FROM reports GROUP BY department')
            stats['department_distribution'] = dict(c.fetchall())
            
            # Recent activity
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            c.execute('SELECT COUNT(*) FROM reports WHERE created_at >= ?', (week_ago,))
            stats['reports_last_7_days'] = c.fetchone()[0]
            
            # Average resolution time
            c.execute('''
                SELECT AVG(JULIANDAY(resolved_at) - JULIANDAY(created_at)) 
                FROM reports 
                WHERE status = "resolved" AND resolved_at IS NOT NULL
            ''')
            avg_days = c.fetchone()[0] or 0
            stats['avg_resolution_days'] = round(avg_days, 2)
            
        except Exception as e:
            print(f"⚠️ Error getting stats: {e}")
            # Return empty stats instead of crashing
            stats = {
                'total_reports': 0,
                'resolved_reports': 0,
                'reports_with_images': 0,
                'status_distribution': {},
                'issue_type_distribution': {},
                'department_distribution': {},
                'reports_last_7_days': 0,
                'avg_resolution_days': 0
            }
        finally:
            conn.close()
        
        return stats
    
    def get_trends_data(self, days=30):
        """Get data for trend analysis"""
        conn = self.get_connection()
        c = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        try:
            # Daily report counts
            c.execute('''
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM reports 
                WHERE created_at >= ?
                GROUP BY DATE(created_at)
                ORDER BY date
            ''', (start_date,))
            
            daily_counts = [{'date': row[0], 'count': row[1]} for row in c.fetchall()]
            
            # Weekly trends by issue type
            c.execute('''
                SELECT 
                    STRFTIME('%Y-%W', created_at) as week,
                    issue_type,
                    COUNT(*) as count
                FROM reports 
                WHERE created_at >= ?
                GROUP BY week, issue_type
                ORDER BY week, issue_type
            ''', (start_date,))
            
            weekly_trends = [{'week': row[0], 'issue_type': row[1], 'count': row[2]} for row in c.fetchall()]
            
        except Exception as e:
            print(f"⚠️ Error getting trends: {e}")
            daily_counts = []
            weekly_trends = []
        finally:
            conn.close()
        
        return {
            'daily_counts': daily_counts,
            'weekly_trends': weekly_trends
        }
    
    def get_reports_geojson(self):
        """Get reports in GeoJSON format for mapping"""
        reports = self.get_reports(per_page=1000)['reports']
        
        features = []
        for report in reports:
            # Only include reports with coordinates
            if report.get('latitude') and report.get('longitude'):
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [report['longitude'], report['latitude']]
                    },
                    "properties": {
                        "id": report['id'],
                        "issue_type": report['issue_type'],
                        "description": report['description'],
                        "location": report['location'],
                        "image_url": report.get('image_url'),
                        "department": report.get('department'),
                        "status": report.get('status', 'received'),
                        "created_at": report['created_at'],
                        "has_image": bool(report.get('image_url'))
                    }
                }
                features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features
        }
    
    # Export Methods
    def export_to_csv(self, filters=None):
        """Export reports to CSV"""
        data = self.get_reports(filters=filters, per_page=10000)
        filename = f'reports_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        if not data['reports']:
            return None
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = data['reports'][0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data['reports'])
        
        return filename
    
    def export_to_json(self, filters=None):
        """Export reports to JSON"""
        data = self.get_reports(filters=filters, per_page=10000)
        filename = f'reports_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, default=str)
        
        return filename
    
    def export_to_excel(self, filters=None):
        """Export reports to Excel format - CSV alternative"""
        # Since we removed pandas, provide CSV as Excel alternative
        print("⚠️ Excel export not available without pandas. Using CSV format instead.")
        return self.export_to_csv(filters)
    
    # Backup and Maintenance
    def backup_database(self, backup_path=None):
        """Create a database backup"""
        try:
            if not backup_path:
                backup_path = f'civicbot_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
            
            conn = self.get_connection()
            backup_conn = sqlite3.connect(backup_path)
            
            conn.backup(backup_conn)
            backup_conn.close()
            conn.close()
            
            print(f"✅ Database backup created: {backup_path}")
            return backup_path
        except Exception as e:
            print(f"❌ Backup error: {e}")
            return None
    
    def cleanup_old_data(self, days_to_keep=365):
        """Archive old data (optional cleanup)"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
            
            conn = self.get_connection()
            c = conn.cursor()
            
            # For now, just mark as archived instead of deleting
            c.execute('''
                UPDATE reports 
                SET status = 'archived' 
                WHERE created_at < ? AND status = 'resolved'
            ''', (cutoff_date,))
            
            affected_rows = c.rowcount
            conn.commit()
            conn.close()
            
            print(f"✅ Archived {affected_rows} old reports")
            return affected_rows
        except Exception as e:
            print(f"❌ Cleanup error: {e}")
            return 0
    
    def update_analytics(self):
        """Update analytics table with current metrics"""
        try:
            stats = self.get_dashboard_stats()
            
            conn = self.get_connection()
            c = conn.cursor()
            
            # Record key metrics
            metrics = [
                ('total_reports', stats['total_reports']),
                ('resolved_reports', stats['resolved_reports']),
                ('resolution_rate', stats['resolved_reports'] / stats['total_reports'] if stats['total_reports'] > 0 else 0),
                ('reports_with_images', stats['reports_with_images']),
                ('reports_last_7_days', stats['reports_last_7_days']),
                ('avg_resolution_days', stats['avg_resolution_days'])
            ]
            
            for metric_name, metric_value in metrics:
                c.execute('''
                    INSERT INTO analytics (metric_name, metric_value, recorded_date)
                    VALUES (?, ?, DATE('now'))
                    ON CONFLICT(metric_name, recorded_date) 
                    DO UPDATE SET metric_value = excluded.metric_value
                ''', (metric_name, metric_value))
            
            conn.commit()
            conn.close()
            print("✅ Analytics updated")
        except Exception as e:
            print(f"⚠️ Analytics update error: {e}")

# Create global instance
db_manager = DatabaseManager()
