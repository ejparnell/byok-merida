import pytest

from merida_api.features.resumes.workspace import DocumentBlock
from merida_api.integrations.pdf_export import LocalPdfArtifacts


def test_published_resume_uses_company_and_environment_user_name(tmp_path):
    export_path = tmp_path / "export"
    pdfs = LocalPdfArtifacts(export_path, user_name="Elizabeth Parnell")
    staged = pdfs.stage(
        (DocumentBlock(kind="heading_1", text="Elizabeth Parnell"),)
    )

    published = pdfs.publish("resume-123", "Acme, Inc.", staged)

    assert published.name == "Acme-Inc-Elizabeth-Parnell.pdf"
    assert published.is_file()
    assert LocalPdfArtifacts(
        export_path, user_name="Elizabeth Parnell"
    ).path("resume-123") == published


def test_removing_published_resume_clears_human_named_artifact(tmp_path):
    export_path = tmp_path / "export"
    pdfs = LocalPdfArtifacts(export_path, user_name="Elizabeth Parnell")
    staged = pdfs.stage(
        (DocumentBlock(kind="heading_1", text="Elizabeth Parnell"),)
    )
    published = pdfs.publish("resume-123", "Acme, Inc.", staged)

    LocalPdfArtifacts(export_path, user_name="Elizabeth Parnell").remove(
        "resume-123"
    )

    assert not published.exists()
    assert pdfs.path("resume-123") is None


def test_publishing_same_company_twice_does_not_overwrite_existing_resume(
    tmp_path,
):
    export_path = tmp_path / "export"
    pdfs = LocalPdfArtifacts(export_path, user_name="Elizabeth Parnell")
    first = pdfs.stage((DocumentBlock(kind="heading_1", text="First"),))
    first_path = pdfs.publish("resume-123", "Acme", first)
    original = first_path.read_bytes()
    second = pdfs.stage((DocumentBlock(kind="heading_1", text="Second"),))

    with pytest.raises(FileExistsError, match="already exists"):
        pdfs.publish("resume-456", "Acme", second)

    assert first_path.read_bytes() == original
    assert pdfs.path("resume-123") == first_path
    assert pdfs.path("resume-456") is None


def test_corrupt_resume_index_does_not_hide_cleanup_failure(tmp_path):
    export_path = tmp_path / "export"
    export_path.mkdir()
    (export_path / ".resume-artifacts.json").write_text("not-json")
    pdfs = LocalPdfArtifacts(export_path, user_name="Elizabeth Parnell")

    with pytest.raises(ValueError):
        pdfs.remove("resume-123")
