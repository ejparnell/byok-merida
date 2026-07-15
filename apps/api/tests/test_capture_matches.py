import asyncio
from datetime import date

from merida_api.features.applications.capture import ApplicationCapture
from merida_api.features.applications.workspace import ApplicationRecord


def application(
    identifier: str,
    *,
    company_name: str,
    role: str,
    status: str = "To Apply",
    date_found: date = date(2026, 7, 15),
) -> ApplicationRecord:
    return ApplicationRecord(
        id=identifier,
        url=f"https://www.notion.so/{identifier}",
        company_name=company_name,
        role=role,
        job_url=f"https://example.test/jobs/{identifier}",
        captured_url=None,
        location=None,
        date_found=date_found,
        application_status=status,
        analyzed=False,
        match_score=None,
    )


class MatchStore:
    def __init__(self, applications: tuple[ApplicationRecord, ...]):
        self.applications = applications

    async def list_active_applications(self) -> tuple[ApplicationRecord, ...]:
        return self.applications


def test_capture_match_recognizes_variants_excludes_archived_and_sorts_newest():
    capture = ApplicationCapture(
        MatchStore(
            (
                application(
                    "older",
                    company_name="Acme, Inc.",
                    role="Senior Engineer",
                    date_found=date(2026, 7, 1),
                ),
                application(
                    "newer",
                    company_name="ACME LLC",
                    role="Sr. Engineer",
                    status="Applied",
                    date_found=date(2026, 7, 14),
                ),
                application(
                    "archived-status",
                    company_name="Acme",
                    role="Senior Engineer",
                    status="Archived",
                ),
                application(
                    "different-role",
                    company_name="Acme",
                    role="Engineering Manager",
                ),
            )
        )
    )

    matches = asyncio.run(capture.find_matches("  Ácme  ", "Sr Engineer"))

    assert [match.id for match in matches] == ["newer", "older"]


def test_capture_match_recognizes_software_engineer_abbreviation_without_fuzzy_match():
    capture = ApplicationCapture(
        MatchStore(
            (
                application(
                    "software-engineer",
                    company_name="Orbit Works",
                    role="Software Engineer",
                ),
                application(
                    "engineering-manager",
                    company_name="Orbit Works",
                    role="Software Engineering Manager",
                ),
            )
        )
    )

    matches = asyncio.run(capture.find_matches("orbit works", "SWE"))

    assert [match.id for match in matches] == ["software-engineer"]
