from __future__ import annotations

import unicodedata


def resume_pdf_filename(company: str, role: str, user: str) -> str:
    components = tuple(_component(value) for value in (company, role, user))
    if not all(components):
        raise ValueError("Company, Role, and User must produce nonempty PDF name components.")
    return "-".join(components) + ".pdf"


def _component(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    output: list[str] = []
    separator_pending = False
    for character in normalized:
        if unicodedata.category(character)[0] in {"L", "N", "M"}:
            if separator_pending and output:
                output.append("-")
            output.append(character)
            separator_pending = False
        else:
            separator_pending = True
    candidate = "".join(output).strip("-")
    encoded = candidate.encode("utf-8")
    if len(encoded) <= 64:
        return candidate
    encoded = encoded[:64]
    while True:
        try:
            candidate = encoded.decode("utf-8")
            break
        except UnicodeDecodeError:
            encoded = encoded[:-1]
    return candidate.rstrip("-")
