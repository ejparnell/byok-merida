import base64
import json


class InvalidCursor(ValueError):
    pass


def encode_cursor(offset: int) -> str:
    payload = json.dumps({"offset": offset}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded).decode())
        offset = value["offset"]
        if not isinstance(offset, int) or offset < 0:
            raise ValueError
        return offset
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise InvalidCursor("Cursor is invalid or expired.") from exc
