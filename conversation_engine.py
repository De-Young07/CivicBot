# conversation_engine.py
import random
import re
from datetime import datetime

class ConversationEngine:
    def __init__(self):
        self.response_templates = self._build_response_templates()
        self.greeting_patterns = self._build_greeting_patterns()
        self.empathy_phrases = self._build_empathy_phrases()
        
    def _build_response_templates(self):
        """Build dynamic response templates with variations"""
        return {
            'report_received': [
                "Thank you for reporting the {issue} at {location}! {empathy} I've logged this with ID #{report_id} and it's been assigned to {department}.",
                "I appreciate you letting us know about the {issue} on {location}. {empathy} Your report #{report_id} is now with {department}.",
                "Thanks for bringing the {issue} at {location} to our attention. {empathy} Report #{report_id} has been created and sent to {department}."
            ],
            'urgent_report': [
                "🚨 I understand this {issue} at {location} is urgent! {empathy} I've prioritized report #{report_id} and alerted {department} immediately.",
                "🚨 Thank you for the urgent report about the {issue} on {location}. {empathy} I've escalated report #{report_id} to {department} for quick action.",
                "🚨 I see this {issue} at {location} needs immediate attention. {empathy} Report #{report_id} has been marked as high priority and sent to {department}."
            ],
            'with_photo': [
                "📸 Thanks for including the photo! It really helps us understand the {issue} at {location}. {empathy} Report #{report_id} is now with {department}.",
                "📸 The photo gives us great context about the {issue} on {location}. {empathy} I've created report #{report_id} and assigned it to {department}.",
                "📸 Thank you for the visual evidence of the {issue} at {location}. {empathy} Report #{report_id} has been logged with {department}."
            ],
            'status_update': [
                "I checked on report #{report_id} for you. The current status is: {status}. {follow_up}",
                "Here's the latest on report #{report_id}: {status}. {follow_up}",
                "I looked up report #{report_id}. The current status is: {status}. {follow_up}"
            ],
            'greeting': [
                "Hello! I'm CivicBot, your friendly neighborhood assistant. I'm here to help you report community issues. What would you like to report today?",
                "Hi there! I'm CivicBot, ready to help you with any community concerns. What issue would you like to report?",
                "Hey! CivicBot here. I can help you report potholes, garbage issues, street light problems, and more. What's on your mind?"
            ],
            'help': [
                "I'm here to help! You can report things like:\n• Potholes or road damage\n• Garbage or sanitation issues\n• Street light outages\n• Water leaks or flooding\n• Graffiti or vandalism\n• Noise disturbances\n\nJust describe what you're seeing and include a location! Photos help too! 📸",
                "Need assistance? I can help with:\n🕳️ Road issues\n🗑️ Trash problems\n💡 Street lights\n💧 Water leaks\n🎨 Graffiti\n👮 Noise complaints\n\nDescribe the issue naturally - I'll understand! You can also include photos for better analysis.",
                "Here's how I can help:\nI understand natural language, so just tell me what you're seeing and where. For example:\n\"There's a large pothole on Main Street\"\n\"Garbage overflowing on Oak Avenue\"\nInclude photos when possible for faster resolution! 📷"
            ],
            'thanks': [
                "You're very welcome! I'm happy to help make our community better. 😊",
                "My pleasure! Feel free to report any other issues you notice. Together we can keep our neighborhood great!",
                "You're welcome! Thanks for being an active community member. Don't hesitate to reach out if you see anything else!"
            ],
            'unknown': [
                "I'm not quite sure what you'd like to report. Could you describe the issue you're seeing? For example, you could say \"pothole on Main Street\" or \"street light out on 5th Avenue.\"",
                "I want to make sure I help you with the right issue. Could you tell me more about what you're seeing? Things like potholes, garbage problems, or street light issues are what I handle best!",
                "Let me help you report that! Could you provide a bit more detail about the issue and location? For example: \"There's a large pothole on Maple Street that needs repair.\""
            ]
        }
    
    def _build_greeting_patterns(self):
        """Patterns to detect greetings"""
        return [
            r'\b(hello|hi|hey|howdy|greetings|good morning|good afternoon|good evening)\b',
            r'\b(what\'s up|sup|yo)\b',
            r'^hi[^a-z]|^hello[^a-z]'
        ]
    
    def _build_empathy_phrases(self):
        """Empathetic phrases to make responses more human"""
        return [
            "I understand how frustrating that can be.",
            "I know these issues can be really inconvenient.",
            "That sounds really concerning.",
            "I appreciate you taking the time to report this.",
            "That must be really annoying to deal with.",
            "I can see why that would be problematic.",
            "Thank you for helping keep our community safe.",
            "I know these situations can be stressful."
        ]
    
    def generate_response(self, message_type, context=None):
        """Generate natural, varied responses based on context"""
        if message_type not in self.response_templates:
            message_type = 'unknown'
        
        template = random.choice(self.response_templates[message_type])
        
        if context:
            # Fill in template variables
            response = template.format(**context)
            
            # Add natural variations
            response = self._add_natural_touches(response, context)
        else:
            response = template
        
        return response
    
    def _add_natural_touches(self, response, context):
        """Add natural language touches to make responses more human"""
        
        # Add occasional follow-up questions for engagement
        follow_ups = [
            " Is there anything else I can help with?",
            " Let me know if you see any updates!",
            " Feel free to check back on the status anytime.",
            " Your report really helps improve our community!"
        ]
        
        # 30% chance to add a follow-up (but not for status updates)
        if context.get('message_type') != 'status_update' and random.random() < 0.3:
            response += random.choice(follow_ups)
        
        # Occasionally add time-based greetings
        if random.random() < 0.2:
            hour = datetime.now().hour
            if 5 <= hour < 12:
                time_greeting = " Have a great morning!"
            elif 12 <= hour < 17:
                time_greeting = " Have a good afternoon!"
            elif 17 <= hour < 22:
                time_greeting = " Have a nice evening!"
            else:
                time_greeting = " Have a good night!"
            
            response += time_greeting
        
        return response
    
    def detect_intent(self, message):
        """Use pattern matching to detect user intent naturally"""
        message_lower = message.lower().strip()
        
        # Check for greetings
        for pattern in self.greeting_patterns:
            if re.search(pattern, message_lower):
                return 'greeting'
        
        # Check for help requests
        if any(word in message_lower for word in ['help', 'what can you do', 'how does this work', 'assist']):
            return 'help'
        
        # Check for thank you
        if any(word in message_lower for word in ['thank', 'thanks', 'appreciate']):
            return 'thanks'
        
        # Check for status requests
        if (message_lower.isdigit() or 
            'status' in message_lower or 
            'update' in message_lower or
            'check' in message_lower):
            return 'status'
        
        # Default to report processing
        return 'report'
    
    def get_empathy_phrase(self):
        """Get a random empathetic phrase"""
        return random.choice(self.empathy_phrases)
    
    def create_report_context(self, analysis, report_id, vision_analysis=None):
        """Create context for report responses"""
        issue_readable = analysis['primary_issue'].replace('_', ' ').title()
        department_readable = analysis['department'].replace('_', ' ').title()
        
        context = {
            'issue': issue_readable,
            'location': analysis['location'],
            'report_id': report_id,
            'department': department_readable,
            'empathy': self.get_empathy_phrase(),
            'urgency': analysis['urgency']
        }
        
        # Add vision analysis info if available
        if vision_analysis and vision_analysis.get('detected_issues'):
            vision_issues = [issue['type'].replace('_', ' ').title() 
                           for issue in vision_analysis['detected_issues'][:2]]
            context['vision_insights'] = f" The photo shows {', '.join(vision_issues)}."
        else:
            context['vision_insights'] = ""
        
        return context