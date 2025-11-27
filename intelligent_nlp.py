# intelligent_nlp.py
import re

class IntelligentCivicNLP:
    def __init__(self):
        self.issue_patterns = self._build_patterns()
    
    def _build_patterns(self):
        return {
            'pothole': ['pothole', 'road damage', 'street damage', 'hole in road'],
            'garbage': ['garbage', 'trash', 'rubbish', 'waste', 'dump'],
            'street_light': ['street light', 'streetlight', 'light out', 'dark street'],
            'water_issue': ['water leak', 'flood', 'leak', 'pipe burst'],
            'graffiti': ['graffiti', 'vandalism', 'spray paint'],
            'other': []
        }
    
    def analyze_message(self, message):
        message_lower = message.lower()
        
        # Simple keyword matching
        for issue_type, keywords in self.issue_patterns.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return {
                        'primary_issue': issue_type,
                        'location': self._extract_location(message),
                        'urgency': 'medium',
                        'department': self._get_department(issue_type),
                        'confidence': 0.8,
                        'all_issues': [issue_type]
                    }
        
        return {
            'primary_issue': 'other',
            'location': 'Unknown',
            'urgency': 'medium',
            'department': 'public_works',
            'confidence': 0.3,
            'all_issues': ['other']
        }
    
    def _extract_location(self, message):
        # Simple location extraction
        location_patterns = [
            r'(?:at|on|near)\s+([^,.!?]+)',
            r'(\d+\s+\w+\s+(?:street|st|avenue|ave|road|rd))'
        ]
        
        for pattern in location_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            if matches:
                return matches[0].strip()
        
        return 'Unknown'
    
    def _get_department(self, issue_type):
        department_map = {
            'pothole': 'public_works',
            'street_light': 'public_works',
            'garbage': 'sanitation',
            'water_issue': 'water_department',
            'graffiti': 'public_works'
        }
        return department_map.get(issue_type, 'public_works')