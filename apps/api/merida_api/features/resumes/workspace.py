from dataclasses import dataclass
from typing import Literal


DocumentBlockKind = Literal[
    "heading_1",
    "heading_2",
    "heading_3",
    "paragraph",
    "quote",
    "callout",
    "bulleted_list_item",
    "numbered_list_item",
    "toggle",
]


@dataclass(frozen=True)
class ResumeRecord:
    id: str
    url: str
    name: str
    application_ids: tuple[str, ...] = ()
    archived: bool = False


@dataclass(frozen=True)
class NoteRecord:
    id: str
    url: str
    name: str
    application_ids: tuple[str, ...] = ()
    resume_ids: tuple[str, ...] = ()
    archived: bool = False


@dataclass(frozen=True)
class DocumentBlock:
    kind: DocumentBlockKind
    text: str
    depth: int = 0


@dataclass(frozen=True)
class ResumeDocument:
    record: ResumeRecord
    blocks: tuple[DocumentBlock, ...]


@dataclass(frozen=True)
class ResumeArtifactBundle:
    resume: tuple[DocumentBlock, ...]
    note: tuple[DocumentBlock, ...]
    pdf_lines: tuple[str, ...]
