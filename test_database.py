# test_database.py
from database_manager import db_manager

def test_database():
    print("🧪 Testing database functionality...")
    
    # Test creating a report
    test_report = {
        'phone': '+1234567890',
        'issue_type': 'pothole',
        'description': 'Test report from verification',
        'location': 'Test Street',
        'department': 'public_works',
        'priority': 'medium'
    }
    
    report_id = db_manager.create_report(test_report)
    print(f"✅ Created test report #{report_id}")
    
    # Test retrieving the report
    report = db_manager.get_report(report_id)
    print(f"✅ Retrieved report: {report['issue_type']} at {report['location']}")
    
    # Test getting stats
    stats = db_manager.get_dashboard_stats()
    print(f"✅ Got stats: {stats['total_reports']} total reports")
    
    # Test getting reports list
    reports_data = db_manager.get_reports(per_page=10)
    print(f"✅ Got {len(reports_data['reports'])} reports")
    
    print("🎉 All database tests passed!")

if __name__ == "__main__":
    test_database()