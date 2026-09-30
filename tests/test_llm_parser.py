import pytest
from llm_parser import LLMQueryParser, parse_llm_output


def test_parses_clean_json():
    text = '{"property_type": "flat", "bedrooms": 2, "location": "maun", "max_price": 4000, "min_price": null}'
    assert parse_llm_output(text) == {
        'property_type': 'flat', 'bedrooms': 2, 'location': 'Maun', 'max_price': 4000,
    }


def test_parses_json_wrapped_in_text_and_strings():
    text = 'Sure! ```json\n{"bedrooms": "3", "max_price": "P5,000"}\n```'
    assert parse_llm_output(text) == {'bedrooms': 3, 'max_price': 5000}


def test_rejects_bad_values():
    text = '{"property_type": "castle", "bedrooms": 50, "location": "", "max_price": -1}'
    assert parse_llm_output(text) == {}


def test_returns_none_for_garbage():
    assert parse_llm_output('no json here') is None
    assert parse_llm_output('{not valid json}') is None


def test_missing_model_dir_is_unavailable(tmp_path):
    parser = LLMQueryParser(model_dir=str(tmp_path / 'nope'))
    assert parser.available is False
    assert parser.parse('2 bedroom house') is None


@pytest.fixture(scope='module')
def real_parser():
    parser = LLMQueryParser()
    if not parser.available:
        pytest.skip('LFM2.5-350M model or torch/transformers not available')
    return parser


@pytest.mark.model
def test_real_model_extracts_filters(real_parser):
    result = real_parser.parse('2 bedroom flat in Maun under P4000')
    print('model output:', result)
    assert result is not None
    assert result.get('bedrooms') == 2
    assert result.get('property_type') == 'flat'
    assert result.get('location') == 'Maun'
    assert result.get('max_price') == 4000


@pytest.mark.model
def test_real_model_handles_words_the_rules_miss(real_parser):
    # "three" is spelled out, which the regex rules can't read
    result = real_parser.parse('three bedroom house in Gaborone')
    print('model output:', result)
    assert result is not None
    assert result.get('bedrooms') == 3
    assert result.get('property_type') == 'house'
