# ai_response_generator.py
import random
import re

class AIResponseGenerator:
    def __init__(self):
        self.personality_traits = self._build_personality()
        self.response_patterns = self._build_response_patterns()
        
    def _build_personality(self):
        """Define the bot's personality traits"""
        return {
            'friendly': True,
            'helpful': True,
            'empathetic': True,
            'professional': True,
            'enthusiastic': True
        }
    
    def _build_response_patterns(self):
        """Patterns for generating dynamic responses"""
        return {
            'acknowledgment': [
                "I see there's {issue} at {location}.",
                "I understand you're reporting {issue} on {location}.",
                "I can see the {issue} situation at {location}.",
                "Noticing the {issue} at {location} you mentioned."
            ],
            'action_taken': [
                "I've gone ahead and created report #{report_id}",
                "I've logged this as report #{report_id}",
                "I've filed this under report #{report_id}",
                "I've documented this in report #{report_id}"
            ],
            'department_info': [
                "and routed it to our {department} team",
                "and assigned it to the {department} department",
                "and sent it over to {department}",
                "and it's now with our {department} specialists"
            ],
            'reassurance': [
                "They'll take it from here and work on resolving this.",
                "They'll review it and take appropriate action.",
                "They're on it and will address this promptly.",
                "They'll handle this and keep things moving forward."
            ],
            'photo_praise': [
                "The photo really helps understand the situation better!",
                "Thanks for including the photo - it gives great context!",
                "The visual evidence is super helpful for assessment!",
                "The photo makes it much easier to evaluate the issue!"
            ]
        }
    
    def generate_ai_response(self, intent, context=None):
        """Generate completely dynamic AI-like responses"""
        
        if intent == 'report_received':
            return self._generate_report_response(context)
        elif intent == 'greeting':
            return self._generate_greeting()
        elif intent == 'help':
            return self._generate_help_response()
        elif intent == 'thanks':
            return self._generate_thanks_response()
        elif intent == 'status_update':
            return self._generate_status_response(context)
        else:
            return self._generate_unknown_response()
    
    def _generate_report_response(self, context):
        """Generate dynamic report acknowledgment"""
        parts = []
        
        # Start with acknowledgment
        acknowledgment = random.choice(self.response_patterns['acknowledgment']).format(
            issue=context['issue'].lower(),
            location=context['location']
        )
        parts.append(acknowledgment)
        
        # Add empathy based on urgency
        if context['urgency'] == 'high':
            urgency_phrases = [
                " This sounds really urgent and concerning.",
                " I can see why this needs immediate attention.",
                " This definitely seems like a high-priority situation."
            ]
            parts.append(random.choice(urgency_phrases))
        
        # Action taken
        action = random.choice(self.response_patterns['action_taken']).format(
            report_id=context['report_id']
        )
        parts.append(action)
        
        # Department routing
        department = random.choice(self.response_patterns['department_info']).format(
            department=context['department']
        )
        parts.append(department)
        
        # Photo praise if applicable
        if context.get('has_photo'):
            parts.append(random.choice(self.response_patterns['photo_praise']))
        
        # Reassurance
        parts.append(random.choice(self.response_patterns['reassurance']))
        
        # Confidence note if low confidence
        if context.get('confidence', 1) < 0.7:
            confidence_notes = [
                f" By the way, I'm about {int(context['confidence']*100)}% sure about the issue type - the team will verify.",
                f" Just to note, I'm {int(context['confidence']*100)}% confident in my assessment here.",
                f" Quick note: I'm {int(context['confidence']*100)}% sure about this classification."
            ]
            parts.append(random.choice(confidence_notes))
        
        return ' '.join(parts)
    
    def _generate_greeting(self):
        """Generate friendly, varied greetings"""
        greetings = [
            "Hey there! 👋 CivicBot here, your friendly neighborhood assistant. I'm all ears (well, code) and ready to help with any community issues you've spotted! What's happening in your area?",
            "Hello! 😊 I'm CivicBot, here to help you report and track community issues. Whether it's potholes, garbage, or anything else - I've got you covered! What would you like to report today?",
            "Hi! I'm CivicBot, your go-to for community concerns. I'm here to make reporting issues easy and effective. What can I help you with right now?",
            "Hey! CivicBot at your service! 🦸 I specialize in helping residents report community issues quickly. What's the situation you're noticing?"
        ]
        return random.choice(greetings)
    
    def _generate_help_response(self):
        """Generate helpful, engaging help responses"""
        help_responses = [
            """I'm your community reporting assistant! Here's what I can help with:

🔧 **Public Works**: Potholes, street lights, road damage
🗑️ **Sanitation**: Garbage overflow, missed pickups, dumping
💧 **Water Dept**: Leaks, flooding, pipe issues
🎨 **Public Property**: Graffiti, vandalism, park issues
👮 **Noise**: Construction noise, disturbances

Just describe what you're seeing naturally - I'll understand! Photos help me understand better too! 📸""",

            """I'm here to help with community issues! Think of me as your digital neighborhood watch.

I understand natural language, so you can say things like:
• "There's a huge pothole on Main Street"
• "Garbage hasn't been collected on Oak Ave"  
• "Street light out at 5th and Elm"
• "Water leaking on Maple Drive"

Include locations and photos when you can! I'll handle the rest.""",

            """Let me help you report community issues! I'm pretty good at understanding:

🏗️ Road and infrastructure problems
🗑️ Trash and sanitation issues  
💡 Street light outages
💧 Water and flood situations
🎨 Vandalism and graffiti
📢 Noise complaints

Just tell me what you're seeing and where. The more details, the better!"""
        ]
        return random.choice(help_responses)
    
    def _generate_thanks_response(self):
        """Generate warm thank you responses"""
        thanks = [
            "You're very welcome! I'm just happy to help make our neighborhood better. Don't hesitate to reach out if you spot anything else! 😊",
            "My pleasure! Thanks for being an awesome community member and taking the time to report this. Together we make a difference!",
            "You're welcome! I appreciate you helping keep our community great. Feel free to report any other issues you notice!",
            "Happy to help! Your report makes our neighborhood better for everyone. Thanks for being so proactive! 🌟"
        ]
        return random.choice(thanks)
    
    def _generate_status_response(self, context):
        """Generate natural status updates"""
        status = context.get('status', 'received')
        report_id = context.get('report_id', '')
        
        status_messages = {
            'received': [
                f"I checked report #{report_id} - it's been received and is waiting for review. The team will look at it soon!",
                f"Report #{report_id} is currently in the queue awaiting assessment. It should be reviewed shortly!",
                f"I see report #{report_id} has been logged and is pending review. Thanks for your patience!"
            ],
            'in-progress': [
                f"Great news! Report #{report_id} is currently being worked on. The team is actively addressing this issue.",
                f"Report #{report_id} is in progress right now! Our crew is on it and making headway.",
                f"I see report #{report_id} is being handled as we speak. The team is working to resolve this!"
            ],
            'resolved': [
                f"Excellent! Report #{report_id} has been completed and resolved. Thanks for helping improve our community! 🎉",
                f"Report #{report_id} is all done! The issue has been resolved. Your report made a difference!",
                f"Good news! Report #{report_id} has been successfully resolved. Thank you for your contribution!"
            ]
        }
        
        return random.choice(status_messages.get(status, ["I'm checking on that report for you..."]))
    
    def _generate_unknown_response(self):
        """Generate helpful responses for unclear messages"""
        unknown_responses = [
            "I want to make sure I help you with the right thing! Could you tell me a bit more about what you're seeing? For example, you could say 'pothole on Main Street' or describe the situation in your own words.",
            "I'm here to help with community issues! Could you describe what you're noticing? Things like road problems, garbage issues, or public property concerns are what I handle best.",
            "Let me help you report that! Could you provide some details about the issue and where it's located? The more specific, the better I can assist!"
        ]
        return random.choice(unknown_responses)