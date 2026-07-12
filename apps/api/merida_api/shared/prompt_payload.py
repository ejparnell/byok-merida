import json
from typing import TypeAlias, Literal

from pydantic import BaseModel


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class EncodedPromptPayload(BaseModel):
    format: Literal["json"]
    format_version: str
    text: str
    source_bytes: int
    encoded_bytes: int


class JsonPromptPayloadEncoder:
    def encode(self, value: JsonValue) -> EncodedPromptPayload:
        text = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        encoded_bytes = len(text.encode("utf-8"))
        return EncodedPromptPayload(
            format="json",
            format_version="json-v1",
            text=text,
            source_bytes=encoded_bytes,
            encoded_bytes=encoded_bytes,
        )
