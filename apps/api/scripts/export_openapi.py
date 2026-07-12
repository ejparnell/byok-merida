import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from merida_api.app import create_app  # noqa: E402
from merida_api.core.settings import Settings  # noqa: E402


def main() -> None:
    output = Path(sys.argv[1])
    with TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        settings = Settings(
            user_name="OpenAPI User",
            export_path=temporary_path / "export",
            recovery_journal_path=temporary_path / "recovery.json",
        )
        schema = create_app(settings).openapi()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
