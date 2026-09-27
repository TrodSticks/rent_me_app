import spacy
import re
from typing import Dict, List, Optional, Any

class PropertySearchEngine:
    """AI-powered property search engine using natural language processing"""
    
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Warning: spaCy English model not found. Using basic text processing.")
            self.nlp = None
        
        # Predefined locations in Botswana
        self.locations = [
            'Gaborone', 'Phakalane', 'Francistown', 'Maun', 'Kasane', 
            'Serowe', 'Molepolole', 'Kanye', 'Mochudi', 'Lobatse', 
            'Palapye', 'Jwaneng', 'Ghanzi', 'Tsabong', 'Letlhakane'
        ]
        
        # Property type synonyms
        self.property_types = {
            'house': ['house', 'home', 'villa', 'cottage', 'bungalow'],
            'flat': ['flat', 'apartment', 'unit', 'condo', 'studio']
        }
        
        # Price keywords and their mappings
        self.price_keywords = {
            'cheap': 3000,
            'affordable': 5000,
            'budget': 4000,
            'expensive': 10000,
            'luxury': 15000,
            'premium': 12000
        }
        
        # Bedroom keywords
        self.bedroom_patterns = [
            r'(\d+)\s*bedroom',
            r'(\d+)\s*bed',
            r'(\d+)\s*br',
            r'(\d+)br',
            r'(\d+)bed'
        ]
        
        # Price patterns
        self.price_patterns = [
            r'under\s*p?(\d+)',
            r'below\s*p?(\d+)',
            r'less\s*than\s*p?(\d+)',
            r'maximum\s*p?(\d+)',
            r'max\s*p?(\d+)',
            r'up\s*to\s*p?(\d+)',
            r'p(\d+)\s*or\s*less',
            r'p(\d+)\s*max'
        ]
    
    def parse_query(self, query: str) -> Dict[str, Any]:
        """Parse natural language search query into structured parameters"""
        query = query.lower().strip()
        
        search_params = {
            'property_type': None,
            'bedrooms': None,
            'location': None,
            'max_price': None,
            'min_price': None,
            'keywords': []
        }
        
        # Extract property type
        search_params['property_type'] = self._extract_property_type(query)
        
        # Extract number of bedrooms
        search_params['bedrooms'] = self._extract_bedrooms(query)
        
        # Extract location
        search_params['location'] = self._extract_location(query)
        
        # Extract price information
        price_info = self._extract_price(query)
        search_params.update(price_info)
        
        # Extract additional keywords using NLP if available
        if self.nlp:
            search_params['keywords'] = self._extract_keywords_nlp(query)
        else:
            search_params['keywords'] = self._extract_keywords_basic(query)
        
        return search_params
    
    def _extract_property_type(self, query: str) -> Optional[str]:
        """Extract property type from query"""
        for prop_type, synonyms in self.property_types.items():
            for synonym in synonyms:
                if synonym in query:
                    return prop_type
        return None
    
    def _extract_bedrooms(self, query: str) -> Optional[int]:
        """Extract number of bedrooms from query"""
        for pattern in self.bedroom_patterns:
            match = re.search(pattern, query)
            if match:
                try:
                    bedrooms = int(match.group(1))
                    if 1 <= bedrooms <= 10:  # Reasonable range
                        return bedrooms
                except ValueError:
                    continue
        return None
    
    def _extract_location(self, query: str) -> Optional[str]:
        """Extract location from query"""
        # Check for exact matches first
        for location in self.locations:
            if location.lower() in query:
                return location
        
        # Check for partial matches
        for location in self.locations:
            if any(part in query for part in location.lower().split()):
                return location
        
        return None
    
    def _extract_price(self, query: str) -> Dict[str, Optional[int]]:
        """Extract price information from query"""
        price_info = {'max_price': None, 'min_price': None}
        
        # Check for price keywords
        for keyword, price in self.price_keywords.items():
            if keyword in query:
                price_info['max_price'] = price
                break
        
        # Check for specific price patterns
        for pattern in self.price_patterns:
            match = re.search(pattern, query)
            if match:
                try:
                    price = int(match.group(1))
                    price_info['max_price'] = price
                    break
                except ValueError:
                    continue
        
        # Check for price ranges
        range_match = re.search(r'p?(\d+)\s*(?:to|-)\s*p?(\d+)', query)
        if range_match:
            try:
                min_price = int(range_match.group(1))
                max_price = int(range_match.group(2))
                price_info['min_price'] = min_price
                price_info['max_price'] = max_price
            except ValueError:
                pass
        
        return price_info
    
    def _extract_keywords_nlp(self, query: str) -> List[str]:
        """Extract keywords using spaCy NLP"""
        doc = self.nlp(query)
        keywords = []
        
        # Extract nouns and adjectives that might be relevant
        for token in doc:
            if (token.pos_ in ['NOUN', 'ADJ'] and 
                not token.is_stop and 
                not token.is_punct and 
                len(token.text) > 2):
                keywords.append(token.lemma_.lower())
        
        # Extract named entities
        for ent in doc.ents:
            if ent.label_ in ['GPE', 'LOC']:  # Geographic entities
                keywords.append(ent.text.lower())
        
        return list(set(keywords))
    
    def _extract_keywords_basic(self, query: str) -> List[str]:
        """Extract keywords using basic text processing"""
        # Remove common stop words
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'i', 'want', 'need', 'looking', 'find'
        }
        
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords
    
    def filter_properties(self, properties: List[Any], search_params: Dict[str, Any]) -> List[Any]:
        """Filter properties based on search parameters"""
        filtered = properties
        
        # Filter by property type
        if search_params['property_type']:
            filtered = [p for p in filtered if p.property_type == search_params['property_type']]
        
        # Filter by bedrooms
        if search_params['bedrooms']:
            filtered = [p for p in filtered if p.bedrooms == search_params['bedrooms']]
        
        # Filter by location
        if search_params['location']:
            location = search_params['location'].lower()
            filtered = [p for p in filtered if location in p.location.lower()]
        
        # Filter by price range
        if search_params['max_price']:
            filtered = [p for p in filtered if p.price <= search_params['max_price']]
        
        if search_params['min_price']:
            filtered = [p for p in filtered if p.price >= search_params['min_price']]
        
        # Filter by keywords (search in title and description)
        if search_params['keywords']:
            keyword_filtered = []
            for prop in filtered:
                text_to_search = f"{prop.title} {prop.description}".lower()
                if any(keyword in text_to_search for keyword in search_params['keywords']):
                    keyword_filtered.append(prop)
            filtered = keyword_filtered
        
        return filtered
    
    def get_search_suggestions(self, partial_query: str) -> List[str]:
        """Generate search suggestions based on partial query"""
        suggestions = [
            "cheap 2 bedroom house in Gaborone",
            "affordable flat in Phakalane",
            "3 bedroom house under P5000",
            "apartment in Francistown",
            "house in Maun",
            "luxury villa in Gaborone",
            "studio apartment under P2000",
            "4 bedroom house in Kasane",
            "budget flat in Serowe",
            "modern apartment in Lobatse"
        ]
        
        if not partial_query or len(partial_query) < 2:
            return suggestions[:5]
        
        # Filter suggestions based on partial query
        partial_lower = partial_query.lower()
        filtered_suggestions = [
            s for s in suggestions 
            if partial_lower in s.lower()
        ]
        
        return filtered_suggestions[:5] if filtered_suggestions else suggestions[:5]

