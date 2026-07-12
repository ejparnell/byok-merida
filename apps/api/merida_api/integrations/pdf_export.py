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
    def __init__(self, export_path: Path):
        self._export_path = export_path

    def stage(self, document: tuple[DocumentBlock, ...]) -> Path:
        staged = self._export_path / f".resume-{uuid.uuid4().hex}.pdf.stage"
        write_resume_pdf(staged, document)
        return staged

    def publish(self, resume_id: str, staged: Path) -> Path:
        path = self._path(resume_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        staged.replace(path)
        return path

    def discard(self, staged: Path) -> None:
        if staged.exists():
            staged.unlink()

    def save(
        self, resume_id: str, document: tuple[DocumentBlock, ...]
    ) -> Path:
        staged = self.stage(document)
        try:
            return self.publish(resume_id, staged)
        finally:
            self.discard(staged)

    def remove(self, resume_id: str) -> None:
        path = self._path(resume_id)
        if path.exists():
            path.unlink()

    def path(self, resume_id: str) -> Path | None:
        path = self._path(resume_id)
        return path if path.exists() else None

    def _path(self, resume_id: str) -> Path:
        safe_id = "".join(
            character if character.isalnum() or character in {"-", "_"} else "-"
            for character in resume_id
        ).strip("-")
        return self._export_path / f"{safe_id or 'resume'}.pdf"
