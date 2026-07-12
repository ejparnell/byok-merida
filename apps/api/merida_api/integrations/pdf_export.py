from pathlib import Path


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text_commands = ["BT", "/F1 12 Tf", "54 750 Td"]
    for index, line in enumerate(lines):
        if index:
            text_commands.append("0 -18 Td")
        text_commands.append(f"({_escape_pdf_text(line)}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
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

    def save(self, resume_id: str, lines: tuple[str, ...]) -> Path:
        path = self._path(resume_id)
        write_simple_pdf(path, list(lines))
        return path

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
