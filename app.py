from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from database import init_db, save_report
from conversation_engine import ConversationEngine
from ai_response_generator import AIResponseGenerator
from database_manager import db_manager
import sqlite3
import requests
from geocoding_service import geocoder
from database_migrator import migrator
from flask import render_template_string, send_file, jsonify
import json
import os
import re
import base64
import json
from datetime import datetime


app = Flask(__name__)

init_db()

print("🔄 Checking database migrations...")
try:
    migrator.migrate_database()
    print("✅ Database migrations completed successfully!")
except Exception as e:
    print(f"❌ Database migration failed: {e}")
    # Don't crash the app, but warn the user
    print("⚠️ Continuing with limited functionality...")

# Now initialize other components
try:
    nlp_engine = IntelligentCivicNLP()
    conversation_engine = ConversationEngine()
    ai_generator = AIResponseGenerator()
    print("✅ All components initialized successfully!")
except Exception as e:
    print(f"❌ Component initialization failed: {e}")
    # Set to None to avoid further errors
    nlp_engine = None
    conversation_engine = None
    ai_generator = None

def analyze_image_with_vision(image_url):
    """Analyze images using Google Cloud Vision API"""
    try:
        # Download image
        response = requests.get(image_url)
        if response.status_code != 200:
            return {"error": "Could not download image"}
        
        # Encode image for Vision API
        image_content = base64.b64encode(response.content).decode('utf-8')
        
        # Get API key from environment
        api_key = os.environ.get('GOOGLE_VISION_API_KEY')
        
        if not api_key:
            return basic_image_analysis(response.content)
        
        # Google Vision API request
        vision_url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
        
        payload = {
            "requests": [
                {
                    "image": {"content": image_content},
                    "features": [
                        {"type": "LABEL_DETECTION", "maxResults": 10},
                        {"type": "OBJECT_LOCALIZATION", "maxResults": 10},
                        {"type": "SAFE_SEARCH_DETECTION", "maxResults": 5}
                    ]
                }
            ]
        }
        
        vision_response = requests.post(vision_url, json=payload)
        
        if vision_response.status_code == 200:
            return parse_vision_results(vision_response.json())
        else:
            print(f"Vision API error: {vision_response.status_code} - {vision_response.text}")
            return basic_image_analysis(response.content)
        
    except Exception as e:
        print(f"Vision analysis error: {e}")
        return basic_image_analysis(response.content if 'response' in locals() else None)

def basic_image_analysis(image_content):
    """Fallback image analysis when no API available"""
    if not image_content:
        return {"analysis_source": "basic", "detected_issues": []}
    
    file_size_kb = len(image_content) / 1024
    
    analysis = {
        "analysis_source": "basic",
        "file_size_kb": round(file_size_kb, 1),
        "quality": "good" if file_size_kb > 100 else "poor",
        "detected_issues": [],
        "safe_for_work": True
    }
    
    return analysis

def parse_vision_results(vision_data):
    """Parse Google Vision API results for civic issues"""
    try:
        if 'responses' not in vision_data or not vision_data['responses']:
            return {"analysis_source": "vision_api", "detected_issues": []}
        
        response = vision_data['responses'][0]
        labels = response.get('labelAnnotations', [])
        objects = response.get('localizedObjectAnnotations', [])
        safe_search = response.get('safeSearchAnnotation', {})
        
        detected_issues = []
        confidence_threshold = 0.7
        
        # Enhanced issue mapping with multiple keywords
        issue_mapping = {
            'pothole': ['pothole', 'road', 'asphalt', 'pavement', 'damage', 'crack'],
            'garbage': ['garbage', 'trash', 'litter', 'waste', 'rubbish', 'dumpster', 'bin'],
            'graffiti': ['graffiti', 'vandalism', 'spray paint', 'tagging', 'wall writing'],
            'water_issue': ['water', 'flood', 'leak', 'flooding', 'pool', 'puddle'],
            'vehicle': ['car', 'vehicle', 'automobile', 'accident', 'traffic'],
            'street_light': ['street light', 'lamp', 'light pole', 'streetlight', 'lamp post'],
            'infrastructure': ['building', 'structure', 'construction', 'scaffolding']
        }
        
        # Analyze labels
        for label in labels:
            label_text = label['description'].lower()
            confidence = label['score']
            
            for issue_type, keywords in issue_mapping.items():
                if any(keyword in label_text for keyword in keywords) and confidence > confidence_threshold:
                    detected_issues.append({
                        'type': issue_type,
                        'confidence': confidence,
                        'source': f"label: {label_text}",
                        'score': confidence
                    })
        
        # Analyze objects
        for obj in objects:
            object_name = obj['name'].lower()
            confidence = obj['score']
            
            for issue_type, keywords in issue_mapping.items():
                if any(keyword in object_name for keyword in keywords) and confidence > confidence_threshold:
                    detected_issues.append({
                        'type': issue_type,
                        'confidence': confidence,
                        'source': f"object: {object_name}",
                        'score': confidence
                    })
        
        # Remove duplicates and sort by confidence
        unique_issues = {}
        for issue in detected_issues:
            if issue['type'] not in unique_issues or issue['score'] > unique_issues[issue['type']]['score']:
                unique_issues[issue['type']] = issue
        
        detected_issues = list(unique_issues.values())
        detected_issues.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            "analysis_source": "google_vision_api",
            "detected_issues": detected_issues,
            "primary_issue": detected_issues[0]['type'] if detected_issues else 'unknown',
            "safe_for_work": safe_search.get('adult', 'UNKNOWN') in ['VERY_UNLIKELY', 'UNLIKELY'],
            "confidence": detected_issues[0]['score'] if detected_issues else 0
        }
        
    except Exception as e:
        print(f"Error parsing vision results: {e}")
        return {"analysis_source": "vision_api", "detected_issues": [], "error": str(e)}



def advanced_nlp_analysis(message):
    """Advanced NLP with entity recognition and sentiment analysis"""
    
    message_lower = message.lower().strip()
    
    # Enhanced pattern matching with confidence scores
    patterns = {
        'pothole': {
            'keywords': ['pothole', 'road damage', 'street damage', 'hole in road', 'road hole', 'asphalt damage', 'cracked road', 'road crack'],
            'weight': 1.0,
            'emergency': False
        },
        'garbage': {
            'keywords': ['garbage', 'trash', 'rubbish', 'waste', 'dump', 'litter', 'cleanup', 'sanitation', 'overflowing bin', 'dumpster'],
            'weight': 0.9,
            'emergency': False
        },
        'street_light': {
            'keywords': ['street light', 'streetlight', 'light out', 'dark street', 'lamp post', 'light pole', 'broken light', 'flickering light'],
            'weight': 0.8,
            'emergency': False
        },
        'water_issue': {
            'keywords': ['water leak', 'flood', 'leak', 'pipe burst', 'drainage', 'sewage', 'overflow', 'water main', 'flooding'],
            'weight': 1.0,
            'emergency': True
        },
        'traffic': {
            'keywords': ['traffic light', 'stop light', 'signal broken', 'road block', 'accident', 'car crash', 'congestion'],
            'weight': 1.0,
            'emergency': True
        },
        'graffiti': {
            'keywords': ['graffiti', 'vandalism', 'spray paint', 'tagging', 'defaced'],
            'weight': 0.7,
            'emergency': False
        }
    }
    
    # Location extraction with multiple patterns
    location_patterns = [
        r'(?:at|on|near|around|beside|opposite)\s+([^,.!?]+)',
        r'(\d+\s+\w+\s+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln))',
        r'(?:location|address)[:\s]+([^,.!?]+)',
        r'in\s+([^,.!?]+?(?:area|neighborhood|district))'
    ]
    
    # Urgency detection
    urgency_indicators = ['urgent', 'emergency', 'asap', 'immediately', 'critical', 'dangerous', 'hazard']
    
    # Analyze the message
    detected_issues = []
    location = 'Unknown'
    urgency_level = 'normal'
    
    # Find issues with confidence scores
    for issue_type, data in patterns.items():
        for keyword in data['keywords']:
            if keyword in message_lower:
                confidence = data['weight']
                # Boost confidence if multiple keywords match
                if sum(1 for k in data['keywords'] if k in message_lower) > 1:
                    confidence += 0.2
                
                detected_issues.append({
                    'type': issue_type,
                    'confidence': min(confidence, 1.0),
                    'emergency': data['emergency']
                })
                break
    
    # Extract location
    for pattern in location_patterns:
        matches = re.findall(pattern, message_lower, re.IGNORECASE)
        if matches:
            location = matches[0].strip()
            if len(location) > 5:  # Reasonable location length
                break
    
    # Detect urgency
    if any(indicator in message_lower for indicator in urgency_indicators):
        urgency_level = 'high'
    elif any(issue['emergency'] for issue in detected_issues):
        urgency_level = 'medium'
    
    # Sort by confidence and get top issue
    if detected_issues:
        detected_issues.sort(key=lambda x: x['confidence'], reverse=True)
        primary_issue = detected_issues[0]
    else:
        primary_issue = {'type': 'other', 'confidence': 0.0, 'emergency': False}
    
    return {
        'primary_issue': primary_issue['type'],
        'confidence': primary_issue['confidence'],
        'all_issues': [issue['type'] for issue in detected_issues],
        'location': location.title() if location != 'Unknown' else 'Unknown',
        'urgency': urgency_level,
        'needs_follow_up': primary_issue['emergency'] or urgency_level in ['high', 'medium']
    }

def geocode_location(location_text):
    """Convert location text to latitude/longitude using OpenStreetMap Nominatim"""
    try:
        if location_text.lower() in ['unknown', '', 'none']:
            return None, None
            
        # Use OpenStreetMap Nominatim API (free)
        base_url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': f"{location_text}",
            'format': 'json',
            'limit': 1
        }
        
        headers = {
            'User-Agent': 'CivicBot/1.0 (Community Service Reporting System)'
        }
        
        response = requests.get(base_url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                print(f"📍 Geocoded '{location_text}' to {lat}, {lon}")
                return lat, lon
        
        print(f"❌ Could not geocode: {location_text}")
        return None, None
        
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None, None

def get_report_status(report_id):
    """Get report status with department info"""
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    c.execute("SELECT status, issue_type, department FROM reports WHERE id = ?", (report_id,))
    result = c.fetchone()
    conn.close()
    return result


@app.route('/')
def home():
    stats = db_manager.get_dashboard_stats()
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>CivicBot - Community Reporting</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
                min-height: 100vh;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 40px 20px;
            }}
            .hero {{
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 60px 40px;
                text-align: center;
                margin-bottom: 40px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                backdrop-filter: blur(10px);
            }}
            .hero h1 {{
                font-size: 3.5em;
                margin-bottom: 20px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-weight: 800;
            }}
            .hero p {{
                font-size: 1.3em;
                color: #666;
                margin-bottom: 30px;
                line-height: 1.6;
            }}
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 25px;
                margin: 50px 0;
            }}
            .stat-card {{
                background: rgba(255, 255, 255, 0.95);
                padding: 30px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
                backdrop-filter: blur(10px);
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
                font-weight: 500;
            }}
            .nav-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 25px;
                margin: 50px 0;
            }}
            .nav-card {{
                background: rgba(255, 255, 255, 0.95);
                padding: 40px 30px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
                text-decoration: none;
                color: inherit;
                backdrop-filter: blur(10px);
            }}
            .nav-card:hover {{
                transform: translateY(-8px);
                box-shadow: 0 20px 40px rgba(0,0,0,0.15);
                text-decoration: none;
                color: inherit;
            }}
            .nav-icon {{
                font-size: 3em;
                margin-bottom: 20px;
            }}
            .nav-card h3 {{
                font-size: 1.5em;
                margin-bottom: 15px;
                color: #333;
                font-weight: 700;
            }}
            .nav-card p {{
                color: #666;
                line-height: 1.6;
            }}
            .cta-section {{
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 50px;
                text-align: center;
                margin: 50px 0;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                backdrop-filter: blur(10px);
            }}
            .cta-button {{
                display: inline-block;
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 18px 36px;
                text-decoration: none;
                border-radius: 50px;
                font-size: 1.2em;
                font-weight: bold;
                transition: all 0.3s ease;
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
                margin: 10px;
            }}
            .cta-button:hover {{
                transform: translateY(-3px);
                box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4);
                color: white;
                text-decoration: none;
            }}
            .footer {{
                text-align: center;
                padding: 40px;
                color: white;
                margin-top: 60px;
            }}
            @media (max-width: 768px) {{
                .hero h1 {{
                    font-size: 2.5em;
                }}
                .container {{
                    padding: 20px 15px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Hero Section -->
            <div class="hero">
                <h1>🤖 CivicBot</h1>
                <p>Your AI-powered assistant for community problem reporting via WhatsApp. Making our neighborhood better, one report at a time.</p>
                <div>
                    <a href="#features" class="cta-button">Explore Features</a>
                    <a href="/map" class="cta-button" style="background: linear-gradient(135deg, #28a745, #20c997);">View Live Map</a>
                </div>
            </div>
            
            <!-- Statistics -->
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{stats['total_reports']}</div>
                    <div class="stat-label">Total Reports</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats['resolved_reports']}</div>
                    <div class="stat-label">Issues Resolved</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats['reports_with_images']}</div>
                    <div class="stat-label">Reports with Photos</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{stats['reports_last_7_days']}</div>
                    <div class="stat-label">Last 7 Days</div>
                </div>
            </div>

            <!-- Navigation Grid -->
            <div id="features" class="nav-grid">
                <a href="/map" class="nav-card">
                    <div class="nav-icon">🗺️</div>
                    <h3>Live Issue Map</h3>
                    <p>Interactive map showing all reported issues with real-time updates, filtering, and detailed information.</p>
                </a>
                
                <a href="/admin" class="nav-card">
                    <div class="nav-icon">📋</div>
                    <h3>Admin Dashboard</h3>
                    <p>Manage all reports, update statuses, assign departments, and track resolution progress.</p>
                </a>
                
                <a href="/admin/stats" class="nav-card">
                    <div class="nav-icon">📊</div>
                    <h3>Statistics & Analytics</h3>
                    <p>Comprehensive analytics with charts, trends, and performance metrics for better decision making.</p>
                </a>
                
                <a href="/admin/advanced" class="nav-card">
                    <div class="nav-icon">⚙️</div>
                    <h3>Advanced Management</h3>
                    <p>Advanced tools for data export, database management, and system configuration.</p>
                </a>
            </div>

            <!-- CTA Section -->
            <div class="cta-section">
                <h2 style="font-size: 2.5em; margin-bottom: 20px; color: #333;">Ready to Get Started?</h2>
                <p style="font-size: 1.2em; color: #666; margin-bottom: 30px;">Start reporting issues or explore the admin tools to manage community concerns.</p>
                <div>
                    <a href="/admin" class="cta-button">Go to Admin Panel</a>
                    <a href="/map" class="cta-button" style="background: linear-gradient(135deg, #28a745, #20c997);">Explore Live Map</a>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>By A4 Analytics - for better communities | CivicBot v1.0</p>
        </div>
    </body>
    </html>
    '''
    
    
@app.route('/webhook', methods=['POST'])
def webhook():
    incoming_msg = request.values.get('Body', '').strip()
    sender_phone = request.values.get('From', '')
    num_media = int(request.values.get('NumMedia', 0))

    print(f"💬 Message from {sender_phone}: {incoming_msg}")
    
    resp = MessagingResponse()
    
    try:
        # Handle greetings
        if incoming_msg.lower() in ['hello', 'hi', 'hey', 'hola', 'hello!', 'hi!']:
            response = "👋 Hello there! I'm CivicBot, your friendly neighborhood assistant! I'm here to help you report community issues like potholes, garbage problems, or street light outages. What would you like to report today?"
        
        # Handle help requests
        elif any(word in incoming_msg.lower() for word in ['help', 'what can you do', 'how does this work']):
            response = """🆘 *Here's how I can help you:*

I can assist with reporting:
🕳️ *Potholes & Road Damage*
🗑️ *Garbage & Sanitation Issues*  
💡 *Street Light Problems*
💧 *Water Leaks & Flooding*
🎨 *Graffiti & Vandalism*

*Just send me:* 
• A description of the issue
• The location (like 'on Main Street')
• A photo if possible! 📸

*Examples:*
'Large pothole on Oak Avenue'
'Garbage overflowing on 5th Street'
'Street light out at Maple Drive'"""
        
        # Handle thank you messages
        elif any(word in incoming_msg.lower() for word in ['thank', 'thanks', 'appreciate']):
            responses = [
                "You're very welcome! 😊 I'm happy to help make our community better.",
                "My pleasure! Thanks for being an awesome community member! 🌟",
                "You're welcome! Together we can keep our neighborhood great!",
                "Happy to help! Don't hesitate to report any other issues you see! 🏘️"
            ]
            import random
            response = random.choice(responses)
        
        # Handle status checks
        elif incoming_msg.isdigit():
            report = db_manager.get_report(int(incoming_msg))
            if report:
                status_emojis = {
                    'received': '📥',
                    'in-progress': '🔄', 
                    'resolved': '✅'
                }
                emoji = status_emojis.get(report['status'], '📋')
                response = f"{emoji} *Report #{incoming_msg}*\n\n*Issue:* {report['issue_type'].replace('_', ' ').title()}\n*Location:* {report['location']}\n*Status:* {report['status'].replace('-', ' ').title()}\n*Submitted:* {report['created_at'][:10]}\n\nWe're on it! Thanks for your patience. 🙏"
            else:
                response = f"❌ I couldn't find a report with ID #{incoming_msg}. Please check the number and try again. If you need help, just type 'help'!"
        
        # Handle image reports
        elif num_media > 0:
            image_url = request.values.get('MediaUrl0')
            
            # Try to analyze the message for issue type and location
            if nlp_engine:
                analysis = nlp_engine.analyze_message(incoming_msg)
                issue_type = analysis['primary_issue']
                location = analysis['location']
                department = analysis['department']
            else:
                issue_type = 'other'
                location = 'Unknown location'
                department = 'public_works'
            
            # Geocode location
            lat, lng = geocoder.geocode_location(location) if 'geocoder' in globals() else (None, None)
            
            # Save report
            report_data = {
                'phone': sender_phone,
                'issue_type': issue_type,
                'description': incoming_msg or 'Photo report',
                'location': location,
                'image_url': image_url,
                'department': department,
                'latitude': lat,
                'longitude': lng
            }
            
            report_id = db_manager.create_report(report_data)
            
            responses = [
                f"📸 *Excellent! Photo received!*\n\nI've logged your {issue_type.replace('_', ' ')} report at {location}.\n*Report ID:* #{report_id}\n\nOur team will review the photo and take appropriate action. Thank you for the visual evidence! 🎯",
                f"📸 *Great photo! Thanks!*\n\nYour {issue_type.replace('_', ' ')} report at {location} has been documented.\n*Tracking ID:* #{report_id}\n\nThe photo really helps us understand the situation better. We'll get on this! 👍",
                f"📸 *Perfect! Visual evidence captured!*\n\nReport #{report_id} has been created for the {issue_type.replace('_', ' ')} at {location}.\n\nYour photo makes it much easier to assess the issue. Thank you for your thorough reporting! 📝"
            ]
            import random
            response = random.choice(responses)
        
        # Handle regular text reports
        else:
            if nlp_engine:
                analysis = nlp_engine.analyze_message(incoming_msg)
                issue_type = analysis['primary_issue']
                location = analysis['location']
                department = analysis['department']
                confidence = analysis['confidence']
            else:
                # Basic keyword matching as fallback
                issue_type = 'other'
                location = 'Unknown location'
                department = 'public_works'
                confidence = 0.5
            
            # Geocode location
            lat, lng = geocoder.geocode_location(location) if 'geocoder' in globals() else (None, None)
            
            # Save report
            report_data = {
                'phone': sender_phone,
                'issue_type': issue_type,
                'description': incoming_msg,
                'location': location,
                'department': department,
                'latitude': lat,
                'longitude': lng
            }
            
            report_id = db_manager.create_report(report_data)
            
            # Build response based on confidence
            if confidence > 0.7:
                base_responses = [
                    f"✅ *Report received!*\n\nI've logged the {issue_type.replace('_', ' ')} at {location}.\n*Report ID:* #{report_id}\n\nOur {department.replace('_', ' ').title()} team has been notified. Thank you for your report! 🏘️",
                    f"📋 *Thank you for reporting!*\n\nYour {issue_type.replace('_', ' ')} issue at {location} is now documented.\n*Tracking ID:* #{report_id}\n\nWe'll work on resolving this. Your community spirit is appreciated! 🌟",
                    f"🎯 *Report submitted successfully!*\n\n{issue_type.replace('_', ' ').title()} at {location} has been recorded.\n*Reference ID:* #{report_id}\n\nThanks for helping keep our neighborhood great! 🙌"
                ]
            else:
                base_responses = [
                    f"📝 *Report logged!*\n\nI've created report #{report_id} for the issue at {location}.\n*Note:* I'm not entirely sure about the issue type, so our team will review it.\n\nThank you for your report! 💫",
                    f"✅ *Got it!*\n\nReport #{report_id} has been created for the situation at {location}.\nOur team will assess the exact issue type and take action.\n\nWe appreciate you speaking up! 🗣️"
                ]
            
            # Add photo suggestion
            photo_tips = [
                "\n\n💡 *Pro tip:* Next time, include a photo for faster resolution! 📸",
                "\n\n📸 *Helpful hint:* Photos help us understand issues better!",
                "\n\n🎯 *FYI:* Visual evidence often leads to quicker action!"
            ]
            import random
            response = random.choice(base_responses) + random.choice(photo_tips)
        
        msg = resp.message(response)
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        # Fallback response
        fallback_responses = [
            "🤖 Oops! I'm having a little trouble right now. Please try again in a moment, or describe your issue in a different way.",
            "⚠️ Sorry, I didn't quite get that. Could you try rephrasing? For example: 'pothole on Main Street' or 'garbage issue on Oak Avenue'.",
            "❌ My apologies! I'm experiencing a temporary issue. Please try your report again, or say 'help' for assistance."
        ]
        import random
        msg = resp.message(random.choice(fallback_responses))
    
    return str(resp)

def _resolve_issue_type(nlp_analysis, vision_analysis):
    """Resolve between NLP and vision analysis"""
    if (vision_analysis and 
        vision_analysis.get('primary_issue') != 'unknown' and
        vision_analysis.get('confidence', 0) > nlp_analysis['confidence']):
        return vision_analysis['primary_issue']
    return nlp_analysis['primary_issue']

@app.route('/admin')
def admin():
    stats = db_manager.get_dashboard_stats()
    reports = db_manager.get_reports(per_page=20)['reports']
    
    html = f'''
    <html>
    <head>
        <title>CivicBot Admin</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .header {{ background: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .nav-buttons {{ display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; }}
            .nav-btn {{ background: #007bff; color: white; padding: 12px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; }}
            .nav-btn:hover {{ background: #0056b3; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
            .stat-card {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .table {{ background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏢 CivicBot Admin Dashboard</h1>
            <p>Manage community reports and track resolution progress</p>
            
            <div class="nav-buttons">
                <a href="/" class="nav-btn">🏠 Home</a>
                <a href="/map" class="nav-btn">🗺️ Live Map</a>
                <a href="/admin/stats" class="nav-btn">📊 Statistics</a>
                <a href="/admin/advanced" class="nav-btn">⚙️ Advanced</a>
                <a href="/admin/export/csv" class="nav-btn">📥 Export CSV</a>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div style="font-size: 2em; font-weight: bold; color: #007bff;">{stats['total_reports']}</div>
                    <div>Total Reports</div>
                </div>
                <div class="stat-card">
                    <div style="font-size: 2em; font-weight: bold; color: #28a745;">{stats['resolved_reports']}</div>
                    <div>Resolved</div>
                </div>
                <div class="stat-card">
                    <div style="font-size: 2em; font-weight: bold; color: #17a2b8;">{stats['reports_with_images']}</div>
                    <div>With Photos</div>
                </div>
                <div class="stat-card">
                    <div style="font-size: 2em; font-weight: bold; color: #ffc107;">{stats['reports_last_7_days']}</div>
                    <div>Last 7 Days</div>
                </div>
            </div>
        </div>

        <div class="table">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Issue Type</th>
                        <th>Location</th>
                        <th>Status</th>
                        <th>Department</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
    '''
    
    for report in reports:
        status_badge = {
            'received': '<span style="background: #ffc107; color: black; padding: 4px 8px; border-radius: 12px; font-size: 12px;">RECEIVED</span>',
            'in-progress': '<span style="background: #17a2b8; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px;">IN PROGRESS</span>',
            'resolved': '<span style="background: #28a745; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px;">RESOLVED</span>'
        }.get(report['status'], report['status'])
        
        html += f'''
                    <tr>
                        <td>#{report['id']}</td>
                        <td>{report['issue_type'].replace('_', ' ').title()}</td>
                        <td>{report['location']}</td>
                        <td>{status_badge}</td>
                        <td>{report.get('department', 'N/A').replace('_', ' ').title()}</td>
                        <td>{report['created_at'][:16].replace('T', ' ')}</td>
                        <td>
                            <a href="/admin/report/{report['id']}" style="background: #6c757d; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 12px;">View</a>
                            <button onclick="updateStatus({report['id']}, 'resolved')" style="background: #28a745; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 12px; cursor: pointer; margin-left: 5px;">Resolve</button>
                        </td>
                    </tr>
        '''
    
    html += '''
                </tbody>
            </table>
        </div>

        <script>
            function updateStatus(reportId, status) {
                if (confirm('Mark report #' + reportId + ' as ' + status + '?')) {
                    fetch('/admin/api/update_report', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({report_id: reportId, status: status})
                    }).then(() => location.reload());
                }
            }
        </script>
    </body>
    </html>
    '''
    
    return html


@app.route('/admin/stats')
def admin_stats():
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    
    # Get various statistics
    c.execute("SELECT COUNT(*) FROM reports")
    total_reports = c.fetchone()[0] or 0  # Ensure it's never None
    
    c.execute("SELECT status, COUNT(*) FROM reports GROUP BY status")
    status_stats = dict(c.fetchall())
    
    c.execute("SELECT issue_type, COUNT(*) FROM reports GROUP BY issue_type")
    issue_stats = dict(c.fetchall())
    
    c.execute("SELECT COUNT(*) FROM reports WHERE image_url IS NOT NULL AND image_url != ''")
    reports_with_images = c.fetchone()[0] or 0
    
    conn.close()
    
    # Safe percentage calculations
    if total_reports > 0:
        image_percentage = (reports_with_images / total_reports) * 100
    else:
        image_percentage = 0
    
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
            .empty-state {{
                background: white;
                padding: 40px;
                text-align: center;
                border-radius: 10px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 CivicBot Analytics</h1>
            <div class="nav">
                <a href="/admin">📋 View All Reports</a>
                <a href="/map">🗺️ View Map</a>
                <a href="/">🏠 Home</a>
            </div>
        </div>
    """
    
    if total_reports == 0:
        html += """
        <div class="empty-state">
            <h2>📊 No Reports Yet</h2>
            <p>When users start sending reports via WhatsApp, statistics will appear here.</p>
            <p>Try sending a message to your bot to create the first report!</p>
        </div>
        """
    else:
        html += f"""
        <div class="stat">
            <h3>📈 Total Reports</h3>
            <p style="font-size: 24px; font-weight: bold; color: #007bff;">{total_reports}</p>
        </div>
        
        <div class="stat">
            <h3>📸 Reports with Photos</h3>
            <p style="font-size: 20px; color: #28a745;">{reports_with_images} ({image_percentage:.1f}% of total)</p>
        </div>
        
        <div class="stat">
            <h3>📊 Status Distribution</h3>
            <ul>
        """
        
        # Add status statistics
        for status, count in status_stats.items():
            percentage = (count / total_reports) * 100
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
            percentage = (count / total_reports) * 100
            html += f'<li><strong>{issue_type.title()}:</strong> {count} reports ({percentage:.1f}%)</li>'
        
        html += """
            </ul>
        </div>
        """
    
    html += """
    </body>
    </html>
    """
    
    return html

# Enhanced Admin Dashboard Routes
@app.route('/admin/advanced')
def advanced_admin():
    """Advanced admin dashboard with data management"""
    stats = db_manager.get_dashboard_stats()
    trends = db_manager.get_trends_data(days=30)
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>CivicBot - Advanced Admin</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            .dashboard-card { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .stat-number { font-size: 2.5em; font-weight: bold; color: #007bff; }
            .nav-pills .nav-link.active { background: #007bff; }
            .export-btn { margin: 5px; }
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <!-- Header -->
            <div class="row bg-primary text-white p-3 mb-4">
                <div class="col">
                    <h1><i class="fas fa-cogs"></i> CivicBot Advanced Admin</h1>
                    <p class="mb-0">Comprehensive Database Management & Analytics</p>
                </div>
            </div>

            <!-- Navigation -->
            <div class="row mb-4">
                <div class="col">
                    <ul class="nav nav-pills">
                        <li class="nav-item">
                            <a class="nav-link active" href="#dashboard" data-bs-toggle="tab">Dashboard</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="#reports" data-bs-toggle="tab">Report Management</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="#analytics" data-bs-toggle="tab">Analytics</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="#export" data-bs-toggle="tab">Data Export</a>
                        </li>
                    </ul>
                </div>
            </div>

            <!-- Tab Content -->
            <div class="tab-content">
                <!-- Dashboard Tab -->
                <div class="tab-pane fade show active" id="dashboard">
                    <div class="row">
                        <!-- Key Metrics -->
                        <div class="col-md-3">
                            <div class="dashboard-card text-center">
                                <i class="fas fa-file-alt fa-2x text-primary mb-2"></i>
                                <div class="stat-number">{{ stats.total_reports }}</div>
                                <div class="text-muted">Total Reports</div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="dashboard-card text-center">
                                <i class="fas fa-check-circle fa-2x text-success mb-2"></i>
                                <div class="stat-number">{{ stats.resolved_reports }}</div>
                                <div class="text-muted">Resolved</div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="dashboard-card text-center">
                                <i class="fas fa-camera fa-2x text-info mb-2"></i>
                                <div class="stat-number">{{ stats.reports_with_images }}</div>
                                <div class="text-muted">With Photos</div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="dashboard-card text-center">
                                <i class="fas fa-chart-line fa-2x text-warning mb-2"></i>
                                <div class="stat-number">{{ stats.reports_last_7_days }}</div>
                                <div class="text-muted">Last 7 Days</div>
                            </div>
                        </div>
                    </div>

                    <!-- Charts -->
                    <div class="row">
                        <div class="col-md-6">
                            <div class="dashboard-card">
                                <h5>Reports by Status</h5>
                                <canvas id="statusChart" height="200"></canvas>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="dashboard-card">
                                <h5>Reports by Issue Type</h5>
                                <canvas id="issueTypeChart" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Report Management Tab -->
                <div class="tab-pane fade" id="reports">
                    <div class="dashboard-card">
                        <h4><i class="fas fa-filter"></i> Report Management</h4>
                        
                        <!-- Filters -->
                        <div class="row mb-3">
                            <div class="col-md-3">
                                <select class="form-select" id="statusFilter">
                                    <option value="">All Statuses</option>
                                    <option value="received">Received</option>
                                    <option value="in-progress">In Progress</option>
                                    <option value="resolved">Resolved</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <select class="form-select" id="issueTypeFilter">
                                    <option value="">All Issue Types</option>
                                    {% for issue_type in stats.issue_type_distribution.keys() %}
                                    <option value="{{ issue_type }}">{{ issue_type.title() }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3">
                                <input type="text" class="form-control" id="searchFilter" placeholder="Search...">
                            </div>
                            <div class="col-md-3">
                                <button class="btn btn-primary w-100" onclick="loadReports()">Apply Filters</button>
                            </div>
                        </div>

                        <!-- Reports Table -->
                        <div id="reportsTable">
                            <!-- Dynamic content will be loaded here -->
                        </div>
                    </div>
                </div>

                <!-- Analytics Tab -->
                <div class="tab-pane fade" id="analytics">
                    <div class="dashboard-card">
                        <h4><i class="fas fa-chart-bar"></i> Advanced Analytics</h4>
                        <div class="row">
                            <div class="col-md-8">
                                <canvas id="trendsChart" height="300"></canvas>
                            </div>
                            <div class="col-md-4">
                                <h6>Performance Metrics</h6>
                                <ul class="list-group">
                                    <li class="list-group-item">
                                        Average Resolution Time
                                        <span class="badge bg-primary float-end">{{ "%.1f"|format(stats.avg_resolution_days) }} days</span>
                                    </li>
                                    <li class="list-group-item">
                                        Resolution Rate
                                        <span class="badge bg-success float-end">
                                            {{ "%.1f"|format((stats.resolved_reports / stats.total_reports * 100) if stats.total_reports > 0 else 0) }}%
                                        </span>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Data Export Tab -->
                <div class="tab-pane fade" id="export">
                    <div class="dashboard-card">
                        <h4><i class="fas fa-download"></i> Data Export</h4>
                        <p>Export your data in various formats for analysis and reporting.</p>
                        
                        <div class="row">
                            <div class="col-md-6">
                                <div class="card">
                                    <div class="card-body">
                                        <h5 class="card-title">Quick Export</h5>
                                        <p class="card-text">Export all current data:</p>
                                        <a href="/admin/export/csv" class="btn btn-success export-btn">
                                            <i class="fas fa-file-csv"></i> CSV Export
                                        </a>
                                        <a href="/admin/export/json" class="btn btn-warning export-btn">
                                            <i class="fas fa-file-code"></i> JSON Export
                                        </a>
                                        <a href="/admin/export/excel" class="btn btn-primary export-btn">
                                            <i class="fas fa-file-excel"></i> Excel Export
                                        </a>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card">
                                    <div class="card-body">
                                        <h5 class="card-title">Database Management</h5>
                                        <p class="card-text">Database maintenance tools:</p>
                                        <a href="/admin/backup" class="btn btn-info export-btn">
                                            <i class="fas fa-database"></i> Create Backup
                                        </a>
                                        <a href="/admin/cleanup" class="btn btn-secondary export-btn" onclick="return confirm('Archive old resolved reports?')">
                                            <i class="fas fa-broom"></i> Cleanup Old Data
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            // Initialize charts
            const statusData = {{ stats.status_distribution | tojson }};
            const issueTypeData = {{ stats.issue_type_distribution | tojson }};
            const trendsData = {{ trends | tojson }};

            // Status Chart
            new Chart(document.getElementById('statusChart'), {
                type: 'doughnut',
                data: {
                    labels: Object.keys(statusData),
                    datasets: [{
                        data: Object.values(statusData),
                        backgroundColor: ['#ffc107', '#17a2b8', '#28a745']
                    }]
                }
            });

            // Issue Type Chart
            new Chart(document.getElementById('issueTypeChart'), {
                type: 'bar',
                data: {
                    labels: Object.keys(issueTypeData).map(k => k.replace('_', ' ').titleCase()),
                    datasets: [{
                        label: 'Reports',
                        data: Object.values(issueTypeData),
                        backgroundColor: '#007bff'
                    }]
                }
            });

            // Load initial reports
            loadReports();

            function loadReports(page = 1) {
                const filters = {
                    status: document.getElementById('statusFilter').value,
                    issue_type: document.getElementById('issueTypeFilter').value,
                    search: document.getElementById('searchFilter').value
                };

                fetch('/admin/api/reports?page=' + page + '&' + new URLSearchParams(filters))
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('reportsTable').innerHTML = data.html;
                    });
            }

            // Helper function for title case
            String.prototype.titleCase = function() {
                return this.split('_').map(word => 
                    word.charAt(0).toUpperCase() + word.slice(1)
                ).join(' ');
            };
        </script>
    </body>
    </html>
    ''', stats=stats, trends=trends)




@app.route('/map')
def interactive_map():
    """Fully functional interactive map"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>CivicBot - Live Issue Map</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #f8f9fa;
            }
            #map { 
                height: 100vh; 
                width: 100%;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 25px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }
            .controls {
                background: white;
                padding: 20px;
                border-bottom: 1px solid #e9ecef;
                display: flex;
                align-items: center;
                gap: 15px;
                flex-wrap: wrap;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .stats-bar {
                background: #343a40;
                color: white;
                padding: 12px 25px;
                display: flex;
                gap: 25px;
                font-size: 14px;
                font-weight: 500;
            }
            .filter-btn {
                background: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 25px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            .filter-btn.active, .filter-btn:hover {
                background: #007bff;
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,123,255,0.3);
            }
            .nav-btn {
                background: #28a745;
                color: white;
                text-decoration: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            .nav-btn:hover {
                background: #218838;
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(40,167,69,0.3);
            }
            .legend {
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                position: absolute;
                bottom: 25px;
                right: 25px;
                z-index: 1000;
                max-width: 280px;
                backdrop-filter: blur(10px);
            }
            .legend-item {
                display: flex;
                align-items: center;
                margin: 8px 0;
                font-size: 13px;
                font-weight: 500;
            }
            .legend-color {
                width: 22px;
                height: 22px;
                border-radius: 50%;
                margin-right: 12px;
                border: 3px solid white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            .loading {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: white;
                padding: 20px 30px;
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                z-index: 1000;
                font-weight: 500;
            }
        </style>
    </head>
    <body>
        <!-- Header -->
        <div class="header">
            <h1 style="margin: 0; font-size: 28px; font-weight: 700;">🗺️ CivicBot Live Issue Map</h1>
            <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 16px;">Real-time visualization of all community reports with interactive filtering</p>
        </div>

        <!-- Statistics Bar -->
        <div class="stats-bar">
            <div>📊 <strong id="total-reports">0</strong> Total Reports</div>
            <div>🕐 Last Updated: <span id="last-updated">Just now</span></div>
            <div>👁️ <span id="visible-reports">0</span> Currently Visible</div>
        </div>

        <!-- Controls -->
        <div class="controls">
            <strong style="color: #495057;">Filter Issues:</strong>
            <button class="filter-btn active" data-issue="all">🌐 All Issues</button>
            <button class="filter-btn" data-issue="pothole">🕳️ Potholes</button>
            <button class="filter-btn" data-issue="garbage">🗑️ Garbage</button>
            <button class="filter-btn" data-issue="street_light">💡 Street Lights</button>
            <button class="filter-btn" data-issue="water_issue">💧 Water Issues</button>
            <button class="filter-btn" data-issue="graffiti">🎨 Graffiti</button>
            <button class="filter-btn" data-issue="other">📋 Other</button>
            
            <div style="margin-left: auto; display: flex; gap: 12px;">
                <a href="/admin" class="nav-btn">📋 Admin Dashboard</a>
                <a href="/admin/stats" class="nav-btn">📊 Statistics</a>
                <a href="/" class="nav-btn">🏠 Home</a>
            </div>
        </div>

        <!-- Map Container -->
        <div id="map">
            <div class="loading">
                <div style="text-align: center;">
                    <div style="font-size: 24px; margin-bottom: 10px;">🗺️</div>
                    <div>Loading interactive map...</div>
                </div>
            </div>
        </div>

        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
        
        <script>
            // Initialize map
            var map = L.map('map').setView([40.7128, -74.0060], 12);
            
            // Add tile layer
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19
            }).addTo(map);
            
            // Create marker cluster group
            var markers = L.markerClusterGroup({
                chunkedLoading: true,
                maxClusterRadius: 50,
                spiderfyOnMaxZoom: true,
                showCoverageOnHover: true
            });
            
            // Issue type styling
            var issueStyles = {
                'pothole': { emoji: '🕳️', color: '#e74c3c', name: 'Pothole' },
                'garbage': { emoji: '🗑️', color: '#f39c12', name: 'Garbage' },
                'street_light': { emoji: '💡', color: '#f1c40f', name: 'Street Light' },
                'water_issue': { emoji: '💧', color: '#3498db', name: 'Water Issue' },
                'graffiti': { emoji: '🎨', color: '#9b59b6', name: 'Graffiti' },
                'noise': { emoji: '📢', color: '#e67e22', name: 'Noise' },
                'traffic': { emoji: '🚦', color: '#d35400', name: 'Traffic' },
                'other': { emoji: '📋', color: '#95a5a6', name: 'Other' }
            };
            
            var statusColors = {
                'received': '#f39c12',    // Orange
                'in-progress': '#3498db', // Blue
                'resolved': '#27ae60'     // Green
            };
            
            var currentMarkers = [];
            var allReports = [];
            
            // Load reports data
            function loadReports() {
                fetch('/api/reports/geojson')
                    .then(response => {
                        if (!response.ok) throw new Error('Network error');
                        return response.json();
                    })
                    .then(data => {
                        document.querySelector('.loading').style.display = 'none';
                        allReports = data.features;
                        updateMap(allReports);
                        updateStats();
                    })
                    .catch(error => {
                        console.error('Error loading reports:', error);
                        document.querySelector('.loading').innerHTML = `
                            <div style="text-align: center; color: #dc3545;">
                                <div style="font-size: 24px; margin-bottom: 10px;">❌</div>
                                <div>Failed to load map data</div>
                                <button onclick="loadReports()" style="margin-top: 10px; padding: 8px 16px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer;">
                                    Retry
                                </button>
                            </div>
                        `;
                    });
            }
            
            // Update map with reports
            function updateMap(reports) {
                // Clear existing markers
                markers.clearLayers();
                currentMarkers = [];
                
                if (reports.length === 0) {
                    // Show message when no reports
                    L.popup()
                        .setLatLng([40.7128, -74.0060])
                        .setContent('<div style="text-align: center; padding: 20px;"><h3>No Reports Yet</h3><p>When reports are made, they will appear here.</p></div>')
                        .openOn(map);
                    return;
                }
                
                reports.forEach(function(feature) {
                    var properties = feature.properties;
                    var style = issueStyles[properties.issue_type] || issueStyles['other'];
                    var statusColor = statusColors[properties.status] || '#95a5a6';
                    
                    // Create custom icon
                    var icon = L.divIcon({
                        html: `
                            <div style="
                                background: ${statusColor};
                                color: white;
                                border: 3px solid ${style.color};
                                border-radius: 50%;
                                width: 48px;
                                height: 48px;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                font-size: 20px;
                                box-shadow: 0 3px 8px rgba(0,0,0,0.3);
                                cursor: pointer;
                                transition: all 0.3s ease;
                            " onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'">
                                ${style.emoji}
                            </div>
                        `,
                        className: 'custom-marker',
                        iconSize: [48, 48],
                        iconAnchor: [24, 24]
                    });
                    
                    var marker = L.marker([
                        feature.geometry.coordinates[1],
                        feature.geometry.coordinates[0]
                    ], { icon: icon });
                    
                    // Create detailed popup
                    var popupContent = `
                        <div style="min-width: 300px; font-family: Arial, sans-serif;">
                            <div style="background: ${style.color}; color: white; padding: 20px; margin: -16px -16px 20px -16px; border-radius: 8px 8px 0 0;">
                                <h3 style="margin: 0; font-size: 20px;">${style.emoji} ${style.name}</h3>
                                <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">Report #${properties.id}</p>
                            </div>
                            
                            <div style="margin-bottom: 20px;">
                                <p style="margin: 0 0 12px 0;"><strong>📍 Location:</strong><br>${properties.location}</p>
                                <p style="margin: 0 0 12px 0;"><strong>📝 Description:</strong><br>${properties.description || 'No description provided'}</p>
                            </div>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px;">
                                <div style="background: #f8f9fa; padding: 12px; border-radius: 6px;">
                                    <strong>Status</strong><br>
                                    <span style="color: ${statusColor}; font-weight: bold; font-size: 12px;">${properties.status.toUpperCase()}</span>
                                </div>
                                <div style="background: #f8f9fa; padding: 12px; border-radius: 6px;">
                                    <strong>Department</strong><br>
                                    <span style="font-size: 12px;">${properties.department ? properties.department.replace('_', ' ').toUpperCase() : 'N/A'}</span>
                                </div>
                            </div>
                            
                            <div style="font-size: 11px; color: #6c757d; margin-bottom: 20px;">
                                Reported: ${new Date(properties.created_at).toLocaleString()}
                                ${properties.has_image ? '<br>📸 Includes photo evidence' : ''}
                            </div>
                            
                            <div style="display: flex; gap: 10px;">
                                <a href="/admin" target="_blank" 
                                   style="flex: 1; background: #007bff; color: white; padding: 10px; text-decoration: none; border-radius: 6px; text-align: center; font-size: 13px; font-weight: 500;">
                                    View Details
                                </a>
                            </div>
                        </div>
                    `;
                    
                    marker.bindPopup(popupContent);
                    markers.addLayer(marker);
                    currentMarkers.push(marker);
                });
                
                map.addLayer(markers);
                
                // Auto-fit map to show all markers with padding
                if (reports.length > 0) {
                    var group = new L.featureGroup(currentMarkers);
                    map.fitBounds(group.getBounds().pad(0.1));
                }
                
                updateVisibleCount();
            }
            
            // Filter reports by issue type
            function filterReports(issueType) {
                if (issueType === 'all') {
                    updateMap(allReports);
                } else {
                    var filtered = allReports.filter(function(feature) {
                        return feature.properties.issue_type === issueType;
                    });
                    updateMap(filtered);
                }
                
                // Update active filter button
                document.querySelectorAll('.filter-btn').forEach(btn => {
                    btn.classList.remove('active');
                });
                event.target.classList.add('active');
            }
            
            // Update statistics
            function updateStats() {
                document.getElementById('total-reports').textContent = allReports.length;
                document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
            }
            
            function updateVisibleCount() {
                document.getElementById('visible-reports').textContent = currentMarkers.length;
            }
            
            // Auto-refresh every 30 seconds
            setInterval(loadReports, 30000);
            
            // Add legend
            var legend = L.control({position: 'bottomright'});
            legend.onAdd = function(map) {
                var div = L.DomUtil.create('div', 'legend');
                div.innerHTML = '<h4 style="margin: 0 0 15px 0; font-size: 16px;">Issue Types</h4>';
                for (var issue in issueStyles) {
                    div.innerHTML += `
                        <div class="legend-item">
                            <div class="legend-color" style="background: ${issueStyles[issue].color}"></div>
                            <span>${issueStyles[issue].emoji} ${issueStyles[issue].name}</span>
                        </div>
                    `;
                }
                div.innerHTML += '<h4 style="margin: 15px 0 10px 0; font-size: 16px;">Status Colors</h4>';
                for (var status in statusColors) {
                    div.innerHTML += `
                        <div class="legend-item">
                            <div class="legend-color" style="background: ${statusColors[status]}"></div>
                            <span>${status.replace('-', ' ').toUpperCase()}</span>
                        </div>
                    `;
                }
                return div;
            };
            legend.addTo(map);
            
            // Initialize
            loadReports();
            
            // Add event listeners for filter buttons
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    filterReports(this.getAttribute('data-issue'));
                });
            });
        </script>
    </body>
    </html>
    '''
    
# Data Management API Endpoints
@app.route('/admin/api/reports')
def admin_api_reports():
    """API endpoint for report management"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')
    issue_type = request.args.get('issue_type')
    search = request.args.get('search')
    
    filters = {}
    if status: filters['status'] = status
    if issue_type: filters['issue_type'] = issue_type
    if search: filters['search'] = search
    
    result = db_manager.get_reports(filters=filters, page=page, per_page=20)
    
    # Generate HTML for the table
    html = '''
    <div class="table-responsive">
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Issue Type</th>
                    <th>Location</th>
                    <th>Status</th>
                    <th>Department</th>
                    <th>Created</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
    '''
    
    for report in result['reports']:
        html += f'''
            <tr>
                <td>#{report['id']}</td>
                <td>{report['issue_type'].replace('_', ' ').title()}</td>
                <td>{report['location']}</td>
                <td>
                    <span class="badge bg-{{
                        'received': 'warning',
                        'in-progress': 'info', 
                        'resolved': 'success'
                    }}[report['status']]">{report['status']}</span>
                </td>
                <td>{report.get('department', '').replace('_', ' ').title()}</td>
                <td>{report['created_at'][:16].replace('T', ' ')}</td>
                <td>
                    <a href="/admin/report/{report['id']}" class="btn btn-sm btn-outline-primary">View</a>
                    <button class="btn btn-sm btn-outline-success" onclick="updateStatus({report['id']}, 'resolved')">Resolve</button>
                </td>
            </tr>
        '''
    
    html += '''
            </tbody>
        </table>
    </div>
    
    <!-- Pagination -->
    <nav>
        <ul class="pagination">
    '''
    
    pagination = result['pagination']
    for p in range(1, pagination['total_pages'] + 1):
        active = 'active' if p == pagination['page'] else ''
        html += f'<li class="page-item {active}"><a class="page-link" href="#" onclick="loadReports({p})">{p}</a></li>'
    
    html += '''
        </ul>
    </nav>
    '''
    
    return jsonify({'html': html, 'pagination': result['pagination']})

@app.route('/admin/export/<format_type>')
def admin_export(format_type):
    """Export data in various formats"""
    if format_type == 'csv':
        filename = db_manager.export_to_csv()
        return send_file(filename, as_attachment=True)
    elif format_type == 'json':
        filename = db_manager.export_to_json()
        return send_file(filename, as_attachment=True)
    elif format_type == 'excel':
        filename = db_manager.export_to_excel()
        if filename:
            return send_file(filename, as_attachment=True)
        else:
            return "Excel export not available", 400
    else:
        return "Invalid format", 400

@app.route('/admin/backup')
def admin_backup():
    """Create database backup"""
    filename = db_manager.backup_database()
    return send_file(filename, as_attachment=True)

@app.route('/admin/cleanup')
def admin_cleanup():
    """Cleanup old data"""
    affected = db_manager.cleanup_old_data(days_to_keep=30)
    return jsonify({'message': f'Archived {affected} old reports', 'affected': affected})

@app.route('/admin/report/<int:report_id>')
def admin_report_detail(report_id):
    """Detailed report view"""
    report = db_manager.get_report(report_id)
    if not report:
        return "Report not found", 404
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Report #{{ report.id }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-4">
            <h2>Report #{{ report.id }}</h2>
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">{{ report.issue_type.replace('_', ' ').title() }}</h5>
                    <p class="card-text"><strong>Description:</strong> {{ report.description }}</p>
                    <p class="card-text"><strong>Location:</strong> {{ report.location }}</p>
                    <p class="card-text"><strong>Status:</strong> <span class="badge bg-{{ 
                        'warning' if report.status == 'received' else 
                        'info' if report.status == 'in-progress' else 
                        'success' 
                    }}">{{ report.status }}</span></p>
                    {% if report.image_url %}
                    <img src="{{ report.image_url }}" class="img-fluid" style="max-height: 300px;">
                    {% endif %}
                </div>
            </div>
            <a href="/admin/advanced" class="btn btn-secondary mt-3">Back to Admin</a>
        </div>
    </body>
    </html>
    ''', report=report)


@app.route('/admin/database-health')
def database_health():
    """Check database health and schema"""
    try:
        schema = migrator.get_database_schema()
        stats = db_manager.get_dashboard_stats()
        
        return jsonify({
            'status': 'healthy',
            'schema': schema,
            'stats': stats,
            'required_columns': {
                'reports': ['phone', 'issue_type', 'location', 'department', 'status'],
                'departments': ['name', 'email', 'phone']
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


# API endpoints for map data
@app.route('/api/reports/geojson')
def api_reports_geojson():
    """API endpoint to get reports in GeoJSON format"""
    from database import get_reports_geojson
    return jsonify(get_reports_geojson())

@app.route('/api/reports/stats')
def api_reports_stats():
    """API endpoint for report statistics"""
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM reports")
    total_reports = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM reports WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    mapped_reports = c.fetchone()[0]
    
    c.execute("SELECT issue_type, COUNT(*) FROM reports GROUP BY issue_type")
    issue_stats = dict(c.fetchall())
    
    conn.close()
    
    return jsonify({
        'total_reports': total_reports,
        'mapped_reports': mapped_reports,
        'issue_stats': issue_stats,
        'last_updated': datetime.now().isoformat()
    })


@app.route('/update_status', methods=['POST'])
def update_status():
    print(f"Received form data: {dict(request.form)}")  # Debug line
    
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
    
    print(f"✅Successfully updated report #{report_id}")
    
    return f'''
    <script>
        alert("✅Status updated for report #{report_id}");
        window.location.href = "/admin";
    </script>
    '''

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



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

