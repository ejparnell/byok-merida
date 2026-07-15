import re
import unicodedata

from .workspace import ApplicationRecord


COMPANY_SUFFIXES = tuple(
    sorted(
        {
            ("ag",),
            ("corporation",),
            ("corp",),
            ("gmbh",),
            ("inc",),
            ("incorporated",),
            ("limited",),
            ("llc",),
            ("llp",),
            ("ltd",),
            ("plc",),
            ("sa",),
            ("sarl",),
            ("bv",),
            ("oy",),
            ("ab",),
            ("pte", "ltd"),
            ("pty", "ltd"),
            ("private", "limited"),
            ("s", "a"),
            ("p", "l", "c"),
            ("l", "l", "p"),
        },
        key=len,
        reverse=True,
    )
)
ROLE_ALIASES = {"sr": ("senior",), "swe": ("software", "engineer")}


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
    tokens = list(_tokens(value))
    while suffix := _matching_suffix(tokens):
        del tokens[-len(suffix) :]
    return " ".join(tokens)


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


def _matching_suffix(tokens: list[str]) -> tuple[str, ...] | None:
    return next(
        (
            suffix
            for suffix in COMPANY_SUFFIXES
            if len(tokens) >= len(suffix) and tuple(tokens[-len(suffix) :]) == suffix
        ),
        None,
    )
