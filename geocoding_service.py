# geocoding_service.py
import requests
import time
import random

class GeocodingService:
    def __init__(self):
        self.cache = {}  # Simple cache to avoid duplicate lookups
        
    def geocode_location(self, location_text):
        """Convert location text to coordinates using multiple services"""
        
        if not location_text or location_text.lower() in ['unknown', 'none', '']:
            return None, None
        
        # Check cache first
        cache_key = location_text.lower().strip()
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Try OpenStreetMap Nominatim first (free)
        lat, lng = self._geocode_nominatim(location_text)
        
        # If that fails, try Google Geocoding as fallback
        if lat is None and os.environ.get('GOOGLE_GEOCODING_API_KEY'):
            lat, lng = self._geocode_google(location_text)
        
        # Cache the result
        self.cache[cache_key] = (lat, lng)
        return lat, lng
    
    def _geocode_nominatim(self, location_text):
        """Use OpenStreetMap Nominatim (free)"""
        try:
            base_url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': location_text,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'CivicBot/1.0 (Community Service Reporting System)',
                'Accept-Language': 'en'
            }
            
            # Be respectful with rate limiting
            time.sleep(1)
            
            response = requests.get(base_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    lat = float(data[0]['lat'])
                    lon = float(data[0]['lon'])
                    print(f"📍 Geocoded '{location_text}' to {lat}, {lon} via OSM")
                    return lat, lon
            
            print(f"❌ OSM geocoding failed for: {location_text}")
            return None, None
            
        except Exception as e:
            print(f"❌ OSM geocoding error: {e}")
            return None, None
    
    def _geocode_google(self, location_text):
        """Use Google Geocoding API as fallback"""
        try:
            api_key = os.environ.get('GOOGLE_GEOCODING_API_KEY')
            if not api_key:
                return None, None
                
            base_url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'address': location_text,
                'key': api_key
            }
            
            response = requests.get(base_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'OK' and data['results']:
                    location = data['results'][0]['geometry']['location']
                    lat = location['lat']
                    lng = location['lng']
                    print(f"📍 Geocoded '{location_text}' to {lat}, {lng} via Google")
                    return lat, lng
            
            return None, None
            
        except Exception as e:
            print(f"❌ Google geocoding error: {e}")
            return None, None
    
    def get_demo_coordinates(self, location_text):
        """Generate demo coordinates for testing when geocoding fails"""
        # Simple hash-based coordinate generation for consistent demo data
        import hashlib
        
        hash_obj = hashlib.md5(location_text.encode())
        hash_int = int(hash_obj.hexdigest()[:8], 16)
        
        # Generate coordinates within a reasonable area
        base_lat = 40.7128  # NYC latitude
        base_lng = -74.0060  # NYC longitude
        
        lat_variation = (hash_int % 1000 - 500) / 10000  # ±0.05 degrees
        lng_variation = ((hash_int // 1000) % 1000 - 500) / 10000  # ±0.05 degrees
        
        demo_lat = base_lat + lat_variation
        demo_lng = base_lng + lng_variation
        
        print(f"📍 Using demo coordinates for '{location_text}': {demo_lat}, {demo_lng}")
        return demo_lat, demo_lng

# Global instance
geocoder = GeocodingService()