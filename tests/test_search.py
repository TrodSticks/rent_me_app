from search_engine import PropertySearchEngine


class FakeLLM:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def parse(self, query):
        self.calls.append(query)
        return self.result


def test_rules_only_parsing():
    params = PropertySearchEngine().parse_query('cheap 2 bedroom house in Gaborone')
    assert params['property_type'] == 'house'
    assert params['bedrooms'] == 2
    assert params['location'] == 'Gaborone'
    assert params['max_price'] == 3000


def test_llm_fills_missing_fields():
    engine = PropertySearchEngine(llm_parser=FakeLLM({'bedrooms': 3}))
    params = engine.parse_query('three bedroom house')
    assert params['bedrooms'] == 3
    assert params['property_type'] == 'house'


def test_llm_does_not_override_rules():
    engine = PropertySearchEngine(llm_parser=FakeLLM({'bedrooms': 5, 'property_type': 'flat'}))
    params = engine.parse_query('2 bedroom house')
    assert params['bedrooms'] == 2
    assert params['property_type'] == 'house'


def test_llm_invented_location_is_ignored():
    engine = PropertySearchEngine(llm_parser=FakeLLM({'location': 'Kasane'}))
    params = engine.parse_query('2 bedroom house')
    assert params['location'] is None


def test_llm_failure_falls_back_to_rules():
    engine = PropertySearchEngine(llm_parser=FakeLLM(None))
    params = engine.parse_query('flat in Maun')
    assert params['property_type'] == 'flat'
    assert params['location'] == 'Maun'


# ---------- Structured, validated output ----------

def test_amenities_and_bathrooms_are_read():
    params = PropertySearchEngine().parse_query('furnished 2 bedroom flat with parking, wi-fi and 2 bathrooms, pets allowed')
    assert params['property_type'] == 'flat'
    assert params['bedrooms'] == 2 and params['bathrooms'] == 2
    assert set(params['amenities']) == {'furnished', 'parking', 'wifi', 'pet_friendly'}


def test_unfurnished_does_not_mean_furnished():
    assert PropertySearchEngine().parse_query('unfurnished house')['amenities'] == []


def test_filter_words_are_not_also_treated_as_keywords():
    params = PropertySearchEngine().parse_query('cheap 2 bedroom house in Gaborone under P4000')
    assert params['keywords'] == []


def test_leftover_words_become_keywords():
    params = PropertySearchEngine().parse_query('modern house in Maun near the river with a garden')
    assert params['keywords'] == ['modern', 'river', 'garden']


def test_words_inside_other_words_are_not_matched():
    params = PropertySearchEngine().parse_query('homely community with units')
    assert params['property_type'] == 'flat'          # "units", not "home" inside "homely"
    assert PropertySearchEngine().parse_query('homely community')['property_type'] is None


def test_room_ranges_are_not_read_as_prices():
    params = PropertySearchEngine().parse_query('2-3 bedroom house')
    assert params['min_price'] is None and params['max_price'] is None


def test_price_range_is_read_and_ordered():
    params = PropertySearchEngine().parse_query('flat 6000 to 3000')
    assert (params['min_price'], params['max_price']) == (3000, 6000)


def test_out_of_range_values_are_dropped():
    params = PropertySearchEngine().parse_query('99 bedroom house under P99999999999999')
    assert params['bedrooms'] is None and params['max_price'] is None


def test_llm_output_is_validated_too():
    engine = PropertySearchEngine(llm_parser=FakeLLM({
        'property_type': 'castle', 'bedrooms': 'three', 'max_price': -5, 'location': 'gaborone',
        'keywords': ['; drop table'], 'something_else': 1}))
    params = engine.parse_query('somewhere in gaborone')
    assert params['property_type'] is None and params['bedrooms'] is None and params['max_price'] is None
    assert params['location'] == 'Gaborone'           # found by the rules; the model's lowercase copy is ignored
    assert 'something_else' not in params
    assert '; drop table' not in params['keywords']


def test_search_text_is_bounded():
    engine = PropertySearchEngine(llm_parser=FakeLLM({}))
    engine.parse_query('garden ' * 1000)
    assert len(engine.llm_parser.calls[0]) <= 200
    assert len(PropertySearchEngine().parse_query(' '.join(f'word{chr(97 + i)}' for i in range(26)))['keywords']) <= 6


def test_empty_search_is_safe():
    params = PropertySearchEngine().parse_query('')
    assert params['keywords'] == [] and params['amenities'] == [] and params['property_type'] is None
