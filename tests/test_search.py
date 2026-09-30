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
