import json

from merida_api.shared.prompt_payload import JsonPromptPayloadEncoder


def test_json_prompt_encoder_preserves_complete_unicode_records():
    value = {
        "records": [
            {
                "id": "evidence-1",
                "text": "Built APIs — safely, with café data.",
            }
        ]
    }

    encoded = JsonPromptPayloadEncoder().encode(value)

    assert encoded.format == "json"
    assert encoded.format_version == "json-v1"
    assert json.loads(encoded.text) == value
    assert "…" not in encoded.text
    assert encoded.source_bytes == encoded.encoded_bytes
