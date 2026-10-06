import re
from typing import Any, Dict, List, Optional

from locations import LOCATIONS, TOWN_COORDS  # noqa: F401  (re-exported for older imports)

try:
    import spacy
except ImportError:
    spacy = None

MAX_QUERY_LENGTH = 200   # longer searches are cut off
MAX_KEYWORDS = 6
MAX_PRICE = 10_000_000


class PropertySearchEngine:
    """Turns a plain-English search into structured, validated filters.

    The rules here always run. An optional LLM parser can fill in what the rules miss;
    search works the same without it.
    """

    def __init__(self, llm_parser=None):
        # Optional LLMQueryParser; fills in filters the rule-based parser misses
        self.llm_parser = llm_parser
        try:
            self.nlp = spacy.load("en_core_web_sm") if spacy else None
        except OSError:
            self.nlp = None
        if self.nlp is None:
            print("Warning: spaCy English model not found. Using basic text processing.")

        self.locations = LOCATIONS

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
            r'(\d+)\s*bedrooms?\b',
            r'(\d+)\s*beds?\b',
            r'(\d+)\s*br\b',
        ]

        self.bathroom_patterns = [
            r'(\d+)\s*bathrooms?\b',
            r'(\d+)\s*baths?\b',
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

        # Phrases that mean an amenity (keys match models.AMENITIES)
        self.amenity_patterns = {
            'parking': r'\b(?:parking|garage|carport)\b',
            'wifi': r'\b(?:wi-?fi|internet)\b',
            'air_conditioning': r'\b(?:air[\s-]?con(?:ditioning|ditioned)?|aircon)\b',
            'furnished': r'(?<!un)\bfurnished\b',
            'security': r'\b(?:security|secure|guarded)\b',
            'pet_friendly': r'\bpets?(?:[\s-]friendly|\s+allowed|\s+welcome)?\b',
            'water_included': r'\bwater\s+included\b',
        }

        # Words that carry no meaning of their own once the filters above are read
        self.stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he', 'in', 'is', 'it',
            'its', 'of', 'on', 'or', 'that', 'the', 'to', 'was', 'will', 'with', 'i', 'me', 'my', 'we',
            'want', 'need', 'looking', 'find', 'search', 'show', 'get', 'any', 'some', 'please',
            'bedroom', 'bedrooms', 'bed', 'beds', 'bathroom', 'bathrooms', 'bath', 'baths', 'room', 'rooms',
            'rent', 'rental', 'rentals', 'renting', 'place', 'places', 'property', 'properties', 'listing',
            'under', 'below', 'less', 'than', 'max', 'maximum', 'min', 'minimum', 'up', 'over', 'above',
            'pula', 'month', 'monthly', 'per', 'price', 'priced', 'near', 'around', 'area', 'town', 'city',
            'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
            'included', 'friendly', 'allowed', 'welcome', 'con', 'conditioning', 'conditioned', 'air',
        }

    def parse_query(self, query: str) -> Dict[str, Any]:
        """Parse a natural language search into structured, validated parameters."""
        query = (query or '')[:MAX_QUERY_LENGTH].lower().strip()

        search_params = {
            'property_type': self._extract_property_type(query),
            'bedrooms': self._extract_count(query, self.bedroom_patterns, 1, 10),
            'bathrooms': self._extract_count(query, self.bathroom_patterns, 1, 10),
            'location': self._extract_location(query),
            'max_price': None,
            'min_price': None,
            'amenities': self._extract_amenities(query),
            'keywords': [],
        }
        search_params.update(self._extract_price(query))

        # Let the LLM fill any filters the rules couldn't find
        if self.llm_parser and query:
            llm_params = self.llm_parser.parse(query) or {}
            if llm_params.get('location') and llm_params['location'].lower() not in query:
                del llm_params['location']  # don't trust invented towns
            for key, value in llm_params.items():
                if key in search_params and search_params[key] is None:
                    search_params[key] = value

        search_params['keywords'] = self._extract_keywords(query)
        return self._validated(search_params)

    def _validated(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Drop anything out of range, whichever parser produced it."""
        if params['property_type'] not in self.property_types:
            params['property_type'] = None
        if params['location'] not in self.locations:
            params['location'] = None
        for key in ('bedrooms', 'bathrooms'):
            value = params[key]
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 10:
                params[key] = None
        for key in ('min_price', 'max_price'):
            value = params[key]
            if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= MAX_PRICE:
                params[key] = None
        if params['min_price'] and params['max_price'] and params['min_price'] > params['max_price']:
            params['min_price'], params['max_price'] = params['max_price'], params['min_price']
        return params

    def _extract_property_type(self, query: str) -> Optional[str]:
        """Extract property type from query"""
        for prop_type, synonyms in self.property_types.items():
            for synonym in synonyms:
                if re.search(rf'\b{synonym}s?\b', query):
                    return prop_type
        return None

    def _extract_count(self, query: str, patterns: List[str], low: int, high: int) -> Optional[int]:
        """A number of rooms, such as "2 bedroom" or "1 bath"."""
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                count = int(match.group(1)[:3])
                if low <= count <= high:
                    return count
        return None

    def _extract_location(self, query: str) -> Optional[str]:
        """Extract location from query"""
        for location in self.locations:
            if re.search(rf'\b{location.lower()}\b', query):
                return location
        return None

    def _extract_amenities(self, query: str) -> List[str]:
        return [key for key, pattern in self.amenity_patterns.items() if re.search(pattern, query)]

    def _extract_price(self, query: str) -> Dict[str, Optional[int]]:
        """Extract price information from query"""
        price_info = {'max_price': None, 'min_price': None}

        # Check for price keywords
        for keyword, price in self.price_keywords.items():
            if re.search(rf'\b{keyword}\b', query):
                price_info['max_price'] = price
                break

        # Check for specific price patterns
        for pattern in self.price_patterns:
            match = re.search(pattern, query)
            if match:
                price_info['max_price'] = int(match.group(1)[:9])
                break

        # Check for price ranges. Three digits or more, so "2-3 bedrooms" isn't read as a price.
        range_match = re.search(r'p?(\d{3,})\s*(?:to|-)\s*p?(\d{3,})', query)
        if range_match:
            price_info['min_price'] = int(range_match.group(1)[:9])
            price_info['max_price'] = int(range_match.group(2)[:9])

        return price_info

    def _extract_keywords(self, query: str) -> List[str]:
        """Words left over once the filters are read, to look for in titles and descriptions."""
        used = set(self.stop_words) | set(self.price_keywords)
        used.update(word for synonyms in self.property_types.values() for word in synonyms)
        used.update(word + 's' for synonyms in self.property_types.values() for word in synonyms)
        used.update(location.lower() for location in self.locations)
        used.update({'parking', 'garage', 'carport', 'wifi', 'wi', 'fi', 'internet', 'aircon', 'furnished',
                     'security', 'secure', 'guarded', 'pet', 'pets', 'water'})

        words = re.findall(r'[a-z]+', query)
        if self.nlp:
            words = [token.lemma_.lower() for token in self.nlp(' '.join(words))]

        keywords = []
        for word in words:
            if len(word) > 2 and word not in used and word not in keywords:
                keywords.append(word[:30])
        return keywords[:MAX_KEYWORDS]

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
            "furnished flat with parking in Gaborone"
        ]

        if not partial_query or len(partial_query) < 2:
            return suggestions[:5]

        # Filter suggestions based on partial query
        partial_lower = partial_query[:MAX_QUERY_LENGTH].lower()
        filtered_suggestions = [
            s for s in suggestions
            if partial_lower in s.lower()
        ]

        return filtered_suggestions[:5] if filtered_suggestions else suggestions[:5]
