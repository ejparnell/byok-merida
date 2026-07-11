import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..applications.schemas import CaptureEvidence


TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def canonicalize_url(raw_url: str) -> str:
    parts = urlsplit(raw_url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def prepare_capture(evidence: CaptureEvidence) -> tuple[dict, str, list[str]]:
    semantic_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", evidence.semantic_html))
    source = (
        evidence.selected_text.strip()
        or evidence.visible_text.strip()
        or html.unescape(semantic_text).strip()
    )
    title = evidence.title.strip()
    match = re.match(r"^(.+?)\s+(?:at|[-|])\s+(.+)$", title, re.IGNORECASE)
    role = match.group(1).strip() if match else title
    company = match.group(2).strip() if match else ""
    errors = []
    if not company:
        errors.append("Company Name could not be parsed with enough confidence.")
    if not role:
        errors.append("Role could not be parsed with enough confidence.")
    if len(source) < 20:
        errors.append("Readable Job Content is required.")

    preview = source[:280] + ("…" if len(source) > 280 else "")
    draft = {
        "jobUrl": canonicalize_url(evidence.url),
        "companyName": company or None,
        "role": role or None,
        "location": None,
        "jobContentPreview": preview,
    }
    return draft, source, errors
