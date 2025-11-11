from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from database import init_db, save_report
import sqlite3
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

init_db()


def analyze_image(image_url):
    """Basic image analysis - you can enhance this with proper AI services"""
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            file_size = len(response.content) / 1024  # Size in KB
            if file_size > 100:  # If image is reasonably large
                return "✅ Image quality appears good for analysis"
            else:
                return "⚠️ Image might be blurry or low quality"
    except:
        pass
    return "Image received!"

def analyze_message(message):
    
    message_lower = message.lower()
    
    # Define patterns for different issue types
    patterns = {
        'pothole': ['pothole', 'road damage', 'street damage', 'hole in road', 'road hole', 'asphalt damage'],
        'garbage': ['garbage', 'trash', 'rubbish', 'waste', 'dump', 'litter', 'cleanup', 'sanitation'],
        'street_light': ['street light', 'streetlight', 'light out', 'dark street', 'lamp post', 'light pole'],
        'water_issue': ['water', 'flood', 'leak', 'pipe', 'drainage', 'sewage', 'overflow'],
        'traffic': ['traffic', 'congestion', 'signal', 'stop light', 'road block', 'accident'],
        'noise': ['noise', 'loud', 'sound', 'disturbance', 'construction noise']
    }
    
    # Location keywords
    location_keywords = ['at ', 'on ', 'near ', 'corner of', 'between', 'street', 'avenue', 'road', 'lane']
    
    # Issue type
    detected_issue = 'other'
    confidence = 0
    
    for issue_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in message_lower:
                detected_issue = issue_type
                confidence += 1
                break
    
    # Location extraction
    location = 'Unknown'
    for loc_keyword in location_keywords:
        if loc_keyword in message_lower:
            # Extract text after location keyword
            start_idx = message_lower.find(loc_keyword) + len(loc_keyword)
            location = message_lower[start_idx:].split('.')[0].split(',')[0].strip()
            if len(location) > 30:  # If too long, truncate
                location = location[:30] + "..."
            break
    
    if detected_issue == 'other' and location != 'Unknown':
        detected_issue = 'general_issue'
    
    return {
        'category': detected_issue,
        'location': location.title() if location != 'Unknown' else 'Unknown',
        'confidence': confidence
    }

def get_report_status(report_id):
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    c.execute("SELECT status, issue_type FROM reports WHERE id = ?", (report_id,))
    result = c.fetchone()
    conn.close()
    return result


@app.route('/')
def home():
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM reports")
    total_reports = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM reports WHERE status='resolved'")
    resolved_reports = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT phone) FROM reports")
    unique_users = c.fetchone()[0]
    conn.close()
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CivicBot - Community Problem Reporting</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
                line-height: 1.6;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            
            .hero {{
                background: white;
                border-radius: 20px;
                padding: 60px 40px;
                text-align: center;
                margin-bottom: 40px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            }}
            
            .hero h1 {{
                font-size: 3.5em;
                margin-bottom: 20px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            
            .hero p {{
                font-size: 1.3em;
                color: #666;
                margin-bottom: 30px;
            }}
            
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 40px 0;
            }}
            
            .stat-card {{
                background: white;
                padding: 30px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
            }}
            
            .stat-card:hover {{
                transform: translateY(-5px);
            }}
            
            .stat-number {{
                font-size: 3em;
                font-weight: bold;
                color: #667eea;
                margin-bottom: 10px;
            }}
            
            .stat-label {{
                font-size: 1.1em;
                color: #666;
            }}
            
            .features {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 30px;
                margin: 50px 0;
            }}
            
            .feature-card {{
                background: white;
                padding: 40px 30px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }}
            
            .feature-icon {{
                font-size: 3em;
                margin-bottom: 20px;
            }}
            
            .feature-card h3 {{
                font-size: 1.5em;
                margin-bottom: 15px;
                color: #333;
            }}
            
            .cta-buttons {{
                text-align: center;
                margin: 50px 0;
            }}
            
            .btn {{
                display: inline-block;
                padding: 15px 30px;
                margin: 0 10px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                text-decoration: none;
                border-radius: 50px;
                font-size: 1.1em;
                font-weight: bold;
                transition: all 0.3s ease;
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            }}
            
            .btn:hover {{
                transform: translateY(-3px);
                box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4);
            }}
            
            .btn-outline {{
                background: white;
                color: #667eea;
                border: 2px solid #667eea;
            }}
            
            .demo-section {{
                background: white;
                border-radius: 20px;
                padding: 50px;
                margin: 40px 0;
                text-align: center;
            }}
            
            .demo-steps {{
                display: flex;
                justify-content: space-around;
                flex-wrap: wrap;
                margin: 40px 0;
            }}
            
            .demo-step {{
                flex: 1;
                min-width: 200px;
                margin: 20px;
                padding: 30px;
            }}
            
            .demo-number {{
                background: #667eea;
                color: white;
                width: 50px;
                height: 50px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.5em;
                font-weight: bold;
                margin: 0 auto 20px;
            }}
            
            footer {{
                text-align: center;
                padding: 40px;
                color: white;
                margin-top: 60px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Hero Section -->
            <div class="hero">
                <h1>CivicBot</h1>
                <p>Your AI-powered assistant for community problem reporting via WhatsApp</p>
                <div class="cta-buttons">
                    <a href="/admin" class="btn">Admin Dashboard</a>
                    <a href="/admin/stats" class="btn btn-outline">View Statistics</a>
                </div>
            </div>
            
            <!-- Statistics -->
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{total_reports}</div>
                    <div class="stat-label">Total Reports</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{resolved_reports}</div>
                    <div class="stat-label">Issues Resolved</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{unique_users}</div>
                    <div class="stat-label">Active Users</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">24/7</div>
                    <div class="stat-label">Always Available</div>
                </div>
            </div>
            
            <!-- Features -->
            <div class="features">
                <div class="feature-card">
                    <div class="feature-icon"></div>
                    <h3>WhatsApp Integration</h3>
                    <p>Report issues directly through WhatsApp - no app installation required!</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon"></div>
                    <h3>Photo Evidence</h3>
                    <p>Attach photos of problems for better understanding and faster resolution</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon"></div>
                    <h3>AI-Powered</h3>
                    <p>Smart categorization and automatic issue detection</p>
                </div>
            </div>
            
            <!-- Demo Section -->
            <div class="demo-section">
                <h2 style="font-size: 2.5em; margin-bottom: 20px; color: #333;">How It Works</h2>
                <p style="font-size: 1.2em; color: #666; margin-bottom: 40px;">Getting started is as easy as sending a WhatsApp message</p>
                
                <div class="demo-steps">
                    <div class="demo-step">
                        <div class="demo-number">1</div>
                        <h3>Send Message</h3>
                        <p>Message our WhatsApp bot with your issue</p>
                    </div>
                    <div class="demo-step">
                        <div class="demo-number">2</div>
                        <h3>Attach Photo</h3>
                        <p>Include a photo of the problem</p>
                    </div>
                    <div class="demo-step">
                        <div class="demo-number">3</div>
                        <h3>Get Tracking ID</h3>
                        <p>Receive instant confirmation with tracking number</p>
                    </div>
                    <div class="demo-step">
                        <div class="demo-number">4</div>
                        <h3>Track Progress</h3>
                        <p>Check status anytime with your report ID</p>
                    </div>
                </div>
                
                <div class="cta-buttons">
                    <a href="https://wa.me/your-twilio-number" class="btn" style="font-size: 1.3em;">
                        Start Chatting on WhatsApp
                    </a>
                </div>
            </div>
        </div>
        <div style="background: #e8f4fd; padding: 20px; border-radius: 10px; margin: 20px 0;">
        <h3>Want to Test CivicBot?</h3>
        <p><em>Send a WhatsApp message to: <strong>+14155238886)</strong></em></p>
        <p><em>With the text: <code>join birth-general</code></em></p>
        </div>
        
        <footer>
            <p>Built by A4 Analytics for better communities | CivicBot v1.0</p>
        </footer>
    </body>
    </html>
    """
    
    
@app.route('/webhook', methods=['POST'])
def webhook():
    incoming_msg = request.values.get('Body', '')
    phone_number = request.values.get('From', '')
    media = int(request.values.get('NumMedia', 0))

    print(f"Received message from {phone_number}: {incoming_msg}")
    
    resp = MessagingResponse()
    
    # Use our free local AI analysis
    analysis = analyze_message(incoming_msg)
    issue_type = analysis['category']
    location = analysis['location']
    
    print(f"Analysis: {analysis}")

    if media > 0:
        image_url = request.values.get('MediaUrl0')
        report_id = save_report(phone_number, issue_type, incoming_msg, location, image_url)
        
        issue_responses = {
            'pothole': f"🕳️ Thank you for reporting the pothole at {location}! Report ID: #{report_id}",
            'garbage': f"🗑️ Thank you for reporting the garbage issue at {location}! Report ID: #{report_id}",
            'street_light': f"💡 Thank you for reporting the street light issue at {location}! Report ID: #{report_id}",
            'water_issue': f"💧 Thank you for reporting the water issue at {location}! Report ID: #{report_id}",
            'traffic': f"🚦 Thank you for reporting the traffic issue at {location}! Report ID: #{report_id}",
            'noise': f"🔊 Thank you for reporting the noise issue at {location}! Report ID: #{report_id}",
            'general_issue': f"📋 Thank you for reporting the issue at {location}! Report ID: #{report_id}",
            'other': f"📋 Thank you for your report! We've logged it with ID: #{report_id}"
        }
        
        response_text = issue_responses.get(issue_type, issue_responses['other'])
        if analysis['confidence'] == 0 and location == 'Unknown':
            response_text += "\n\n💡 Tip: For faster service, include the location in your message!"
            
        msg = resp.message(response_text)
    
    elif incoming_msg.isdigit():
        # Status checking feature
        report_info = get_report_status(int(incoming_msg))
        if report_info:
            status, issue_type = report_info
            status_messages = {
                'received': f"📋 Report #{incoming_msg} ({issue_type}) is received and awaiting review",
                'in-progress': f"🔄 Report #{incoming_msg} ({issue_type}) is currently being addressed",
                'resolved': f"✅ Report #{incoming_msg} ({issue_type}) has been resolved!"
            }
            msg = resp.message(status_messages.get(status, f"Report #{incoming_msg} status: {status}"))
        else:
            msg = resp.message("❌ Report ID not found. Please check your report number.")
    
    elif 'hello' in incoming_msg.lower() or 'hi' in incoming_msg.lower():
        msg = resp.message("""Hello! I'm CivicBot 🤖

I can help you report:
🕳️ Potholes & Road damage
🗑️ Garbage & Sanitation issues  
💡 Street light problems
💧 Water leaks & Flooding
🚦 Traffic & Signal issues
🔊 Noise disturbances

Just send a photo with a description and location!""")
    
    elif 'help' in incoming_msg.lower():
        msg = resp.message("""🆘 **CivicBot Help**

📸 **To report an issue:** Send a photo with a description
Example: "Large pothole on Main Street near the park"

🔍 **Check status:** Send your report number
Example: "123"

📍 **Include location** for faster service!
Example: "on Oak Avenue", "near city hall", "at 5th and Main"

We support: potholes, garbage, street lights, water issues, traffic, noise, and more!""")
    
    else:
        msg = resp.message("I can help you report civic issues! 📸 Send a photo of the problem with a description and location. Type 'help' for more options.")

    return str(resp)

@app.route('/admin')
def admin_dashboard():
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    c.execute("SELECT * FROM reports ORDER BY created_at DESC")
    reports = c.fetchall()
    conn.close()
    
    # Using f-strings to avoid formatting conflicts
    html = f"""
    <html>
    <head>
        <title>CivicBot Admin</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .header {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }}
            .report {{ background: white; border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .status-received {{ border-left: 5px solid #ffc107; }}
            .status-in-progress {{ border-left: 5px solid #17a2b8; }}
            .status-resolved {{ border-left: 5px solid #28a745; }}
            .image {{ max-width: 300px; max-height: 200px; margin: 10px 0; border-radius: 5px; }}
            .btn {{ background: #007bff; color: white; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; }}
            .nav {{ margin: 20px 0; }}
            .nav a {{ background: #6c757d; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px; margin-right: 10px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏢 CivicBot Admin Dashboard</h1>
            <p>Total Reports: <strong>{len(reports)}</strong></p>
            <div class="nav">
                <a href="/admin/stats">📊 View Statistics</a>
                <a href="/">🏠 Home</a>
            </div>
        </div>
        <div class="reports">
    """
    
    if not reports:
        html += """
        <div class="report">
            <h3>No reports yet</h3>
            <p>When users send reports via WhatsApp, they will appear here.</p>
        </div>
        """
    else:
        for report in reports:
            # report structure: [id, phone, issue_type, description, location, image_url, status, created_at]
            report_id = report[0]
            phone = report[1] or 'N/A'
            issue_type = report[2] or 'Unknown Issue'
            description = report[3] or 'No description'
            location = report[4] or 'Unknown location'
            image_url = report[5]  # This is the image_url field
            status = report[6] or 'received'
            created_at = report[7] or 'Unknown date'
            
            status_class = f"status-{status}"
            
            # Image HTML if available
            image_html = ""
            if image_url:
                image_html = f'''
                <div style="margin: 10px 0;">
                    <strong>📸 Photo Evidence:</strong><br>
                    <img src="{image_url}" class="image" alt="Report Photo" 
                         onerror="this.style.display='none'">
                </div>
                '''
            
            html += f"""
            <div class="report {status_class}">
                <h3>📋 Report #{report_id} - {issue_type.title()}</h3>
                <p><strong>📞 From:</strong> {phone}</p>
                <p><strong>📝 Description:</strong> {description}</p>
                <p><strong>📍 Location:</strong> {location}</p>
                {image_html}
                <p><strong>🔄 Status:</strong> {status.upper()}</p>
                <p><strong>📅 Submitted:</strong> {created_at}</p>
                
                <form action="/update_status" method="post" style="margin-top: 15px;">
                    <input type="hidden" name="report_id" value="{report_id}">
                    <label><strong>Update Status:</strong></label>
                    <select name="status">
                        <option value="received" {'selected' if status=='received' else ''}>📥 Received</option>
                        <option value="in-progress" {'selected' if status=='in-progress' else ''}>🔄 In Progress</option>
                        <option value="resolved" {'selected' if status=='resolved' else ''}>✅ Resolved</option>
                    </select>
                    <button type="submit" class="btn">Update</button>
                </form>
            </div>
            """
    
    html += """
        </div>
    </body>
    </html>
    """
    return html

@app.route('/admin/stats')
def admin_stats():
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    
    # Get various statistics
    c.execute("SELECT COUNT(*) FROM reports")
    total_reports = c.fetchone()[0]
    
    c.execute("SELECT status, COUNT(*) FROM reports GROUP BY status")
    status_stats = dict(c.fetchall())
    
    c.execute("SELECT issue_type, COUNT(*) FROM reports GROUP BY issue_type")
    issue_stats = dict(c.fetchall())
    
    c.execute("SELECT COUNT(*) FROM reports WHERE image_url IS NOT NULL")
    reports_with_images = c.fetchone()[0]
    
    conn.close()
    
    # FIXED: Proper string formatting for CSS
    html = f"""
    <html>
    <head>
        <title>CivicBot Analytics</title>
        <style>
            body {{ 
                font-family: Arial; 
                margin: 20px; 
                background: #f5f5f5;
            }}
            .stat {{ 
                background: #f8f9fa; 
                padding: 15px; 
                margin: 10px 0;
                border-radius: 5px;
                border-left: 4px solid #007bff;
            }}
            .header {{
                background: white;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .nav a {{
                background: #6c757d;
                color: white;
                padding: 10px 15px;
                text-decoration: none;
                border-radius: 4px;
                margin-right: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 CivicBot Analytics</h1>
            <div class="nav">
                <a href="/admin">📋 View All Reports</a>
                <a href="/">🏠 Home</a>
            </div>
        </div>
        
        <div class="stat">
            <h3>📈 Total Reports</h3>
            <p style="font-size: 24px; font-weight: bold; color: #007bff;">{total_reports}</p>
        </div>
        
        <div class="stat">
            <h3>📸 Reports with Photos</h3>
            <p style="font-size: 20px; color: #28a745;">{reports_with_images} ({reports_with_images/total_reports*100:.1f}% of total)</p>
        </div>
        
        <div class="stat">
            <h3>📊 Status Distribution</h3>
            <ul>
    """
    
    # Add status statistics
    for status, count in status_stats.items():
        percentage = (count / total_reports) * 100 if total_reports > 0 else 0
        html += f'<li><strong>{status.title()}:</strong> {count} reports ({percentage:.1f}%)</li>'
    
    html += """
            </ul>
        </div>
        
        <div class="stat">
            <h3>🔧 Issue Types</h3>
            <ul>
    """
    
    # Add issue type statistics
    for issue_type, count in issue_stats.items():
        percentage = (count / total_reports) * 100 if total_reports > 0 else 0
        html += f'<li><strong>{issue_type.title()}:</strong> {count} reports ({percentage:.1f}%)</li>'
    
    html += """
            </ul>
        </div>
    </body>
    </html>
    """
    
    return html

@app.route('/debug-routes')
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': rule.rule
        })
    
    html = "<h1>Registered Routes:</h1><ul>"
    for route in routes:
        html += f"<li><strong>{route['path']}</strong> - {route['methods']}</li>"
    html += "</ul>"
    return html

@app.route('/update_status', methods=['POST'])
def update_status():
    print(f"📨 Received form data: {dict(request.form)}")  # Debug line
    
    report_id = request.form.get('report_id')
    new_status = request.form.get('status')
    
    if not report_id or not new_status:
        return "❌ Missing report ID or status", 400
    
    print(f"🔄 Updating report #{report_id} to status: {new_status}")
    
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    c.execute("UPDATE reports SET status = ? WHERE id = ?", (new_status, report_id))
    conn.commit()
    conn.close()
    
    print(f"✅ Successfully updated report #{report_id}")
    
    return f'''
    <script>
        alert("✅ Status updated for report #{report_id}");
        window.location.href = "/admin";
    </script>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)



