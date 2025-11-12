from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from database import init_db, save_report
import sqlite3
import requests
import json
import os
import re
import base64
import json
from datetime import datetime


app = Flask(__name__)

init_db()



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
    sender_phone = request.values.get('From', '')
    num_media = int(request.values.get('NumMedia', 0))

    print(f"📩 Received from {sender_phone}: {incoming_msg}")
    
    resp = MessagingResponse()
    
    # Use ADVANCED NLP analysis
    analysis = advanced_nlp_analysis(incoming_msg)
    issue_type = analysis['primary_issue']
    location = analysis['location']
    confidence = analysis['confidence']
    urgency_level = analysis['urgency']
    all_issues = analysis['all_issues']
    
    print(f"🤖 NLP Analysis: {analysis}")

    # Enhanced urgency handling
    if urgency_level == 'high':
        urgency_note = "🚨 URGENT: This has been flagged as high priority! "
        priority_emoji = "🚨"
    elif urgency_level == 'medium':
        urgency_note = "⚠️ Priority: This issue has been elevated. "
        priority_emoji = "⚠️"
    else:
        urgency_note = ""
        priority_emoji = ""

    # Enhanced response templates
    response_templates = {
        'pothole': f"{urgency_note}🕳️ Thank you for reporting the pothole at {{location}}! ",
        'garbage': f"{urgency_note}🗑️ Thank you for reporting the garbage issue at {{location}}! ",
        'water_issue': f"{urgency_note}💧 Thank you for reporting the water issue at {{location}}! ",
        'traffic': f"{urgency_note}🚦 Thank you for reporting the traffic issue at {{location}}! ",
        'street_light': f"{urgency_note}💡 Thank you for reporting the street light issue at {{location}}! ",
        'graffiti': f"{urgency_note}🎨 Thank you for reporting the graffiti at {{location}}! ",
        'other': f"{urgency_note}📋 Thank you for your report at {{location}}! ",
    }

    # In your webhook function, replace the image processing section:
if num_media > 0:
    image_url = request.values.get('MediaUrl0')
    print(f"🖼️ Processing image: {image_url}")
    
    # Analyze the image with Computer Vision
    vision_analysis = analyze_image_with_vision(image_url)
    print(f"👁️ Vision Analysis: {vision_analysis}")
    
    # Combine NLP and Vision analysis intelligently
    nlp_confidence = analysis['confidence']
    vision_confidence = vision_analysis.get('confidence', 0)
    
    if (vision_analysis.get('primary_issue') and 
        vision_analysis['primary_issue'] != 'unknown' and 
        vision_confidence > 0.6 and 
        vision_confidence > nlp_confidence):
        # Vision analysis is more confident, use it
        final_issue_type = vision_analysis['primary_issue']
        analysis_source = " (AI Image Analysis)"
        confidence_note = f"👁️ AI Vision is {int(vision_confidence*100)}% confident"
    else:
        # Use NLP analysis
        final_issue_type = analysis['primary_issue']
        analysis_source = " (Text Analysis)"
        confidence_note = f"🤖 AI Text is {int(nlp_confidence*100)}% confident"
    
    
    lat, lng = geocode_location(location)
    report_id = save_report(sender_phone, final_issue_type, incoming_msg, location, image_url, lat, lng)    
    
    # Build enhanced response
    template = response_templates.get(final_issue_type, response_templates['other'])
    response_text = f"📸 {urgency_note}Image analyzed{analysis_source}!\n"
    response_text += template.format(location=location)
    response_text += f"\n\n📋 Report ID: #{report_id}"
    response_text += f"\n{confidence_note}"
    
    # Add vision insights if available
    if vision_analysis.get('detected_issues'):
        vision_issues = [issue['type'] for issue in vision_analysis['detected_issues'][:3]]
        unique_issues = list(set(vision_issues))
        if len(unique_issues) > 1:
            response_text += f"\n\n🔍 AI detected: {', '.join(unique_issues)}"
    
    # Add follow-up for urgent issues
    if analysis['needs_follow_up']:
        response_text += f"\n\n{priority_emoji} This has been marked for immediate attention!"
    
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
    
    elif 'hello' in incoming_msg.lower() or 'hi' in incoming_msg.lower() or 'hey' in incoming_msg.lower():
        msg = resp.message("""🤖 Hello! I'm CivicBot - your AI-powered community assistant!

I can help you report:
🕳️ Potholes & Road damage
🗑️ Garbage & Sanitation issues  
💡 Street light problems
💧 Water leaks & Flooding
🚦 Traffic & Signal issues
🎨 Graffiti & Vandalism

📸 *Send a photo with a description* for fastest service!
📍 Include location like "on Main Street" or "near the park"

Try: "There's a large pothole on Oak Street" + photo""")
    
    elif 'help' in incoming_msg.lower():
        msg = resp.message("""🆘 **CivicBot Help Guide**

📝 **How to Report:**
• Send a photo + description
• Include location in your message
• Example: "Large pothole on Main Street near park"

🔍 **Check Status:**
• Send your report number
• Example: "123"

🚨 **Urgent Issues:**
Use words like: *urgent, emergency, dangerous, asap*

📍 **Location Tips:**
• "on Oak Avenue"
• "near city hall" 
• "at 5th and Main Street"
• "in Central Park"

📞 **Need human help?** Your report will be reviewed by our team!""")
    
    elif 'thank' in incoming_msg.lower():
        msg = resp.message("""You're welcome! 😊 

I'm here to help make our community better. Feel free to report any issues you see!""")
    
    else:
        # For text-only reports without images
        if issue_type != 'other' or location != 'Unknown':
            report_id = save_report(sender_phone, issue_type, incoming_msg, location)
            
            template = response_templates.get(issue_type, response_templates['other'])
            response_text = template.format(location=location)
            response_text += f"\n\n📋 Report ID: #{report_id}"
            
            # Add photo suggestion
            response_text += "\n\n📸 *Tip: Next time include a photo for faster resolution!*"
            
            # Add confidence note
            if confidence < 0.7:
                response_text += f"\n💡 I'm {int(confidence*100)}% sure about the issue type."
            
            msg = resp.message(response_text)
        else:
            # Generic response for unclear messages
            msg = resp.message("""🤔 I'm not sure what you'd like to report.

Try sending:
• A photo of the issue + description
• Or be more specific like:
  "Pothole on Main Street"
  "Garbage overflowing on Oak Ave"
  "Street light out at 5th Street"

Type *help* for more options!""")

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

@app.route('/map')
def map_dashboard():
    """Interactive map showing all reports with real geolocation"""
    conn = sqlite3.connect('civicbot.db')
    c = conn.cursor()
    
    # Get reports with coordinates
    c.execute("""
        SELECT id, issue_type, description, location, latitude, longitude, status, created_at, image_url 
        FROM reports 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY created_at DESC
    """)
    reports = c.fetchall()
    conn.close()
    
    # Convert to GeoJSON
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
                "status": report[6],
                "created_at": report[7],
                "has_image": bool(report[8])
            }
        }
        features.append(feature)
    
    geojson_data = json.dumps({
        "type": "FeatureCollection",
        "features": features
    })
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>CivicBot - Live Issue Map</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
        <style>
            #map {{ height: 70vh; width: 100%; }}
            body {{ margin: 0; font-family: Arial, sans-serif; }}
            .header {{ background: #2c3e50; color: white; padding: 20px; }}
            .controls {{ background: #34495e; padding: 15px; color: white; }}
            .legend {{ background: white; padding: 10px; border-radius: 5px; position: absolute; bottom: 20px; right: 20px; z-index: 1000; }}
            .cluster-marker {{ background: #e74c3c; color: white; border-radius: 50%; text-align: center; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🗺️ CivicBot Live Issue Map</h1>
            <p>Real-time visualization of community reports with AI analysis</p>
        </div>
        
        <div class="controls">
            <a href="/admin" style="color: white; margin-right: 15px;">📋 List View</a>
            <a href="/admin/stats" style="color: white; margin-right: 15px;">📊 Statistics</a>
            <a href="/" style="color: white;">🏠 Home</a>
        </div>

        <div id="map"></div>

        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
        <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
        
        <script>
            // Initialize map
            var map = L.map('map').setView([7.97156, 3.613074], 12);
            
            // Add tile layer
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap contributors'
            }}).addTo(map);
            
            // Create marker cluster group
            var markers = L.markerClusterGroup();
            
            // Issue type icons and colors
            var issueStyles = {{
                'pothole': {{icon: '🕳️', color: '#e74c3c'}},
                'garbage': {{icon: '🗑️', color: '#f39c12'}},
                'water_issue': {{icon: '💧', color: '#3498db'}},
                'traffic': {{icon: '🚦', color: '#9b59b6'}},
                'street_light': {{icon: '💡', color: '#f1c40f'}},
                'graffiti': {{icon: '🎨', color: '#e67e22'}},
                'other': {{icon: '📋', color: '#95a5a6'}}
            }};
            
            var statusColors = {{
                'received': '#f39c12',
                'in-progress': '#3498db',
                'resolved': '#27ae60'
            }};
            
            // Add reports to map
            var reports = {geojson_data};
            
            reports.features.forEach(function(feature) {{
                var style = issueStyles[feature.properties.issue_type] || issueStyles['other'];
                var statusColor = statusColors[feature.properties.status] || '#95a5a6';
                
                // Create custom icon
                var icon = L.divIcon({{
                    html: `<div style="background: ${{statusColor}}; color: white; border: 3px solid ${{style.color}}; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 18px;">${{style.icon}}</div>`,
                    className: 'custom-marker',
                    iconSize: [40, 40],
                    iconAnchor: [20, 20]
                }});
                
                var marker = L.marker([
                    feature.geometry.coordinates[1],
                    feature.geometry.coordinates[0]
                ], {{icon: icon}});
                
                // Create popup content
                var popupContent = `
                    <div style="min-width: 250px;">
                        <h3>${{style.icon}} Report #${{feature.properties.id}}</h3>
                        <p><strong>Type:</strong> ${{feature.properties.issue_type}}</p>
                        <p><strong>Status:</strong> <span style="color: ${{statusColor}}; font-weight: bold;">${{feature.properties.status}}</span></p>
                        <p><strong>Location:</strong> ${{feature.properties.location}}</p>
                        <p><strong>Description:</strong> ${{feature.properties.description}}</p>
                        <p><strong>Reported:</strong> ${{new Date(feature.properties.created_at).toLocaleDateString()}}</p>
                        ${{feature.properties.has_image ? '<p>📸 <em>Includes photo evidence</em></p>' : ''}}
                        <div style="margin-top: 10px;">
                            <a href="/admin" target="_blank" style="background: #3498db; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">View Details</a>
                        </div>
                    </div>
                `;
                
                marker.bindPopup(popupContent);
                markers.addLayer(marker);
            }});
            
            map.addLayer(markers);
            
            // Auto-fit map to show all markers
            if (reports.features.length > 0) {{
                map.fitBounds(markers.getBounds(), {{ padding: [20, 20] }});
            }}
            
            // Add legend
            var legend = L.control({{position: 'bottomright'}});
            legend.onAdd = function(map) {{
                var div = L.DomUtil.create('div', 'legend');
                div.innerHTML = '<h4>Issue Types</h4>';
                for (var issue in issueStyles) {{
                    div.innerHTML += '<div style="margin: 5px 0;"><span style="font-size: 20px; margin-right: 5px;">' + issueStyles[issue].icon + '</span> ' + issue + '</div>';
                }}
                div.innerHTML += '<h4 style="margin-top: 15px;">Status</h4>';
                for (var status in statusColors) {{
                    div.innerHTML += '<div style="margin: 5px 0;"><span style="display: inline-block; width: 15px; height: 15px; background: ' + statusColors[status] + '; margin-right: 5px;"></span> ' + status + '</div>';
                }}
                return div;
            }};
            legend.addTo(map);
        </script>
    </body>
    </html>
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
