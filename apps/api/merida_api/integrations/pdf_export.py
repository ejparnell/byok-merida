import json
from pathlib import Path
import textwrap
import uuid

from ..features.resumes.workspace import DocumentBlock


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _safe_pdf_text(value: str) -> str:
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u00a0": " ",
    }
    return "".join(replacements.get(character, character) for character in value)


def _document_lines(document: tuple[DocumentBlock, ...]):
    output: list[tuple[str, int, int]] = []
    for block in document:
        if block.kind == "heading_1":
            prefix, size, leading, width = "", 18, 24, 58
        elif block.kind in {"heading_2", "heading_3"}:
            prefix, size, leading, width = "", 14, 20, 72
        elif block.kind in {"bulleted_list_item", "numbered_list_item"}:
            prefix, size, leading, width = "- ", 10, 14, 88
        else:
            prefix, size, leading, width = "", 10, 14, 92
        wrapped = textwrap.wrap(
            _safe_pdf_text(block.text),
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        for index, line in enumerate(wrapped):
            output.append((f"{prefix if index == 0 else '  '}{line}", size, leading))
        if block.kind in {"heading_1", "heading_2", "heading_3"}:
            output.append(("", 8, 8))
    return output


def write_resume_pdf(path: Path, document: tuple[DocumentBlock, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pages: list[list[tuple[str, int, int]]] = [[]]
    remaining = 690
    for line in _document_lines(document):
        if remaining - line[2] < 36 and pages[-1]:
            pages.append([])
            remaining = 690
        pages[-1].append(line)
        remaining -= line[2]

    page_ids = [4 + index * 2 for index in range(len(pages))]
    content_ids = [page_id + 1 for page_id in page_ids]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for page_id, content_id, lines in zip(page_ids, content_ids, pages, strict=True):
        del page_id
        text_commands = ["BT", "54 744 Td"]
        current_size = None
        for line, size, leading in lines:
            if size != current_size:
                text_commands.append(f"/F1 {size} Tf")
                current_size = size
            text_commands.append(f"({_escape_pdf_text(line)}) Tj")
            text_commands.append(f"0 -{leading} Td")
        text_commands.append("ET")
        stream = "\n".join(text_commands).encode("latin-1", errors="replace")
        objects.extend(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode(),
                b"<< /Length "
                + str(len(stream)).encode()
                + b" >>\nstream\n"
                + stream
                + b"\nendstream",
            )
        )
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{number} 0 obj\n".encode())
        content.extend(obj)
        content.extend(b"\nendobj\n")
    xref = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode())
    content.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.write_bytes(content)


class LocalPdfArtifacts:
    def __init__(self, export_path: Path, *, user_name: str):
        self._export_path = export_path
        self._user_name = user_name
        self._index_path = export_path / ".resume-artifacts.json"

    def stage(self, document: tuple[DocumentBlock, ...]) -> Path:
        staged = self._export_path / f".resume-{uuid.uuid4().hex}.pdf.stage"
        write_resume_pdf(staged, document)
        return staged

    def publish(self, resume_id: str, company_name: str, staged: Path) -> Path:
        path = self._export_path / self._filename(company_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        previous_index = self._load_index()
        existing_owners = {
            key for key, value in previous_index.items() if value == path.name
        }
        if path.exists() and resume_id not in existing_owners:
            raise FileExistsError(
                f"A resume PDF already exists at {path.name}."
            )
        index = {
            key: value
            for key, value in previous_index.items()
            if value != path.name or key == resume_id
        }
        index[resume_id] = path.name
        self._save_index(index)
        try:
            staged.replace(path)
        except Exception:
            self._save_index(previous_index)
            raise
        return path

    def discard(self, staged: Path) -> None:
        if staged.exists():
            staged.unlink()

    def remove(self, resume_id: str) -> None:
        path = self._path(resume_id)
        if path.exists():
            path.unlink()
        index = self._load_index()
        if resume_id in index:
            del index[resume_id]
            self._save_index(index)

    def path(self, resume_id: str) -> Path | None:
        path = self._path(resume_id)
        return path if path.exists() else None

    def _path(self, resume_id: str) -> Path:
        filename = self._load_index().get(resume_id)
        if filename and Path(filename).name == filename:
            return self._export_path / filename
        return self._legacy_path(resume_id)

    def _legacy_path(self, resume_id: str) -> Path:
        safe_id = "".join(
            character if character.isalnum() or character in {"-", "_"} else "-"
            for character in resume_id
        ).strip("-")
        return self._export_path / f"{safe_id or 'resume'}.pdf"

    def _filename(self, company_name: str) -> str:
        company = _filename_component(company_name) or "Company"
        user = _filename_component(self._user_name)
        if not user:
            raise ValueError("USER_NAME must be configured before exporting resumes.")
        return f"{company}-{user}.pdf"

    def _load_index(self) -> dict[str, str]:
        if not self._index_path.is_file():
            return {}
        payload = json.loads(self._index_path.read_text())
        if not isinstance(payload, dict):
            raise ValueError("Resume PDF index must contain a JSON object.")
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            raise ValueError("Resume PDF index contains an invalid entry.")
        return payload

    def _save_index(self, index: dict[str, str]) -> None:
        self._export_path.mkdir(parents=True, exist_ok=True)
        temporary = self._export_path / f".resume-artifacts-{uuid.uuid4().hex}.tmp"
        try:
            temporary.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
            temporary.replace(self._index_path)
        finally:
            if temporary.exists():
                temporary.unlink()


def _filename_component(value: str) -> str:
    output = []
    pending_separator = False
    for character in value.strip():
        if character.isalnum():
            if pending_separator and output:
                output.append("-")
            output.append(character)
            pending_separator = False
        else:
            pending_separator = True
    return "".join(output)
