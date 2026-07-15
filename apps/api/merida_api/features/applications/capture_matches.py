import re
import unicodedata

from .workspace import ApplicationRecord


COMPANY_SUFFIXES = frozenset(
    {
        "ag",
        "corporation",
        "corp",
        "gmbh",
        "inc",
        "incorporated",
        "limited",
        "llc",
        "ltd",
        "plc",
        "sa",
    }
)
ROLE_ALIASES = {"jr": ("junior",), "sr": ("senior",), "swe": ("software", "engineer")}


def find_capture_matches(
    applications: tuple[ApplicationRecord, ...], company_name: str, role: str
) -> tuple[ApplicationRecord, ...]:
    expected_company = normalize_company_name(company_name)
    expected_role = normalize_role(role)
    if not expected_company or not expected_role:
        return ()
    return tuple(
        sorted(
            (
                application
                for application in applications
                if application.application_status != "Archived"
                and normalize_company_name(application.company_name) == expected_company
                and normalize_role(application.role) == expected_role
            ),
            key=lambda application: (application.date_found, application.id),
            reverse=True,
        )
    )


def normalize_company_name(value: str) -> str:
    return " ".join(
        token for token in _tokens(value) if token not in COMPANY_SUFFIXES
    )


def normalize_role(value: str) -> str:
    normalized: list[str] = []
    for token in _tokens(value):
        normalized.extend(ROLE_ALIASES.get(token, (token,)))
    return " ".join(normalized)


def _tokens(value: str) -> tuple[str, ...]:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    return tuple(re.findall(r"[a-z0-9]+", ascii_value.lower()))
