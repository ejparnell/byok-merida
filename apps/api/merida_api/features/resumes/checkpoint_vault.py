from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CheckpointAuthorityError(RuntimeError):
    """Protected Resume checkpoint authority is unavailable or invalid."""


@dataclass(frozen=True)
class CheckpointBinding:
    kind: str
    schema_version: int
    run_id: str
    source_proof: str
    candidate_ordinal: int | None = None
    producing_call_id: str | None = None
    artifact_set_id: str | None = None

    def associated_data(self) -> bytes:
        return json.dumps(
            {
                "artifactSetId": self.artifact_set_id,
                "candidateOrdinal": self.candidate_ordinal,
                "kind": self.kind,
                "producingCallId": self.producing_call_id,
                "runId": self.run_id,
                "schemaVersion": self.schema_version,
                "sourceProof": self.source_proof,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")


@dataclass(frozen=True)
class EncryptedCheckpoint:
    key_version: str
    nonce: bytes
    ciphertext: bytes


class ResumeCheckpointVault:
    """AES-256-GCM protection for the three private Resume checkpoint kinds."""

    def __init__(self, keys: dict[str, bytes], *, current_key_version: str):
        if current_key_version not in keys:
            raise CheckpointAuthorityError("The current checkpoint key is unavailable.")
        if not keys or any(len(key) != 32 for key in keys.values()):
            raise CheckpointAuthorityError("Resume checkpoint keys must be 256 bits.")
        self._keys = dict(keys)
        self._current = current_key_version

    @classmethod
    def from_base64(cls, value: str, *, key_version: str) -> "ResumeCheckpointVault":
        try:
            key = base64.b64decode(value, validate=True)
        except (ValueError, TypeError) as error:
            raise CheckpointAuthorityError("The Resume checkpoint key is malformed.") from error
        return cls({key_version: key}, current_key_version=key_version)

    def seal(self, binding: CheckpointBinding, document: dict[str, Any]) -> EncryptedCheckpoint:
        plaintext = json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._keys[self._current]).encrypt(
            nonce, plaintext, binding.associated_data()
        )
        return EncryptedCheckpoint(self._current, nonce, ciphertext)

    def open(self, binding: CheckpointBinding, checkpoint: EncryptedCheckpoint) -> dict[str, Any]:
        key = self._keys.get(checkpoint.key_version)
        if key is None:
            raise CheckpointAuthorityError("The checkpoint key version is unavailable.")
        try:
            plaintext = AESGCM(key).decrypt(
                checkpoint.nonce,
                checkpoint.ciphertext,
                binding.associated_data(),
            )
            document = json.loads(plaintext)
        except (InvalidTag, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CheckpointAuthorityError("The Resume checkpoint could not be authenticated.") from error
        if not isinstance(document, dict):
            raise CheckpointAuthorityError("The Resume checkpoint payload is invalid.")
        return document

    def rotate(
        self, binding: CheckpointBinding, checkpoint: EncryptedCheckpoint
    ) -> EncryptedCheckpoint:
        return self.seal(binding, self.open(binding, checkpoint))
