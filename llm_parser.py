import json
import os
import re
from typing import Any, Dict, Optional

MODEL_ID = 'LiquidAI/LFM2.5-350M'
MODEL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'LFM2.5-350M')

PROMPT = """Extract rental search filters from the user's query.
Reply with ONLY a JSON object with these keys:
"property_type": "house" or "flat" or null,
"bedrooms": integer or null,
"location": town name or null,
"max_price": integer in Pula or null,
"min_price": integer in Pula or null

Query: {query}"""


class LLMQueryParser:
    """Parses search queries with the local LiquidAI LFM2.5-350M model.

    The model is loaded lazily on first use. If torch/transformers or the
    model files are missing, `available` is False and parse() returns None.
    """

    def __init__(self, model_dir: str = MODEL_DIR):
        self.model_dir = model_dir
        self._model = None
        self._tokenizer = None
        self._load_failed = False

    @property
    def available(self) -> bool:
        return self._load()

    def _load(self) -> bool:
        if self._model is not None:
            return True
        if self._load_failed:
            return False
        if not os.path.isdir(self.model_dir):
            print("AI search model not found; using rule-based search. "
                  "Run `python download_model.py` to enable it.")
            self._load_failed = True
            return False
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
            self._model = AutoModelForCausalLM.from_pretrained(self.model_dir)
            self._model.eval()
            return True
        except Exception as e:
            print(f"Warning: could not load LLM search model: {e}")
            self._load_failed = True
            return False

    def generate(self, query: str, max_new_tokens: int = 80) -> str:
        import torch
        messages = [{'role': 'user', 'content': PROMPT.format(query=query)}]
        inputs = self._tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors='pt', return_dict=True
        )
        with torch.no_grad():
            output = self._model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        new_tokens = output[0][inputs['input_ids'].shape[1]:]
        return self._tokenizer.decode(new_tokens, skip_special_tokens=True)

    def parse(self, query: str) -> Optional[Dict[str, Any]]:
        if not query or not self._load():
            return None
        try:
            return parse_llm_output(self.generate(query))
        except Exception as e:
            print(f"Warning: LLM search parsing failed: {e}")
            return None


def parse_llm_output(text: str) -> Optional[Dict[str, Any]]:
    """Pull the first JSON object out of model output and sanitise its values."""
    match = re.search(r'\{.*?\}', text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    result = {}
    prop_type = data.get('property_type')
    if isinstance(prop_type, str) and prop_type.lower() in ('house', 'flat'):
        result['property_type'] = prop_type.lower()

    bedrooms = _to_int(data.get('bedrooms'))
    if bedrooms is not None and 1 <= bedrooms <= 10:
        result['bedrooms'] = bedrooms

    location = data.get('location')
    if isinstance(location, str) and location.strip():
        result['location'] = location.strip().title()

    for key in ('max_price', 'min_price'):
        price = _to_int(data.get(key))
        if price is not None and price > 0:
            result[key] = price

    return result


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r'[^\d]', '', value)
        return int(digits) if digits else None
    return None
