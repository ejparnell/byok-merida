import argparse
import asyncio
import sys

import uvicorn

from .app import create_app
from .core.settings import Settings
from .shared.recovery import JsonEffectJournal, RecoveryJournalError


def _run_targeted_reconciliation(settings: Settings, run_id: str) -> None:
    journal = JsonEffectJournal(settings.recovery_journal_path)
    entry = journal.get(run_id)
    if entry is None or entry.resolution != "active":
        return
    app = create_app(settings)

    async def reconcile() -> None:
        if entry.workflow == "capture":
            await app.state.capture.reconcile(run_id=run_id)
        elif entry.workflow == "resume_creation":
            await app.state.resumes.reconcile(run_id=run_id)

    asyncio.run(reconcile())


def run_recovery_command(
    settings: Settings,
    action: str,
    *,
    run_id: str | None = None,
    confirmed: bool = False,
) -> int:
    try:
        journal = JsonEffectJournal(settings.recovery_journal_path)
    except RecoveryJournalError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if action == "inspect":
        entries = journal.unresolved()
        if not entries:
            print("No unresolved recovery entries.")
            return 0
        for entry in entries:
            print(
                f"{entry.run_id} workflow={entry.workflow} "
                f"domain={entry.domain_key} phase={entry.phase} "
                f"started={entry.started_at} updated={entry.updated_at} "
                f"application={entry.application_id or '-'} "
                f"resume={entry.resume_id or '-'} note={entry.note_id or '-'} "
                f"pdf={entry.pdf_id or '-'} cleanup={entry.cleanup_status} "
                f"cleanup_codes={','.join(entry.cleanup_errors) or '-'} "
                "next=verify the listed artifacts, then run targeted reconcile"
            )
        return 0
    if action == "reconcile":
        if not run_id or not confirmed:
            print(
                "Reconciliation requires --run-id and --yes.",
                file=sys.stderr,
            )
            return 2
        _run_targeted_reconciliation(settings, run_id)
        return 0
    if action == "acknowledge":
        if not run_id or not confirmed:
            print(
                "Acknowledgement requires --run-id and --yes after operator recovery.",
                file=sys.stderr,
            )
            return 2
        entry = journal.get(run_id)
        if entry is None or entry.resolution != "active":
            print("Recovery entry is not active.", file=sys.stderr)
            return 2
        _run_targeted_reconciliation(settings, run_id)
        journal = JsonEffectJournal(settings.recovery_journal_path)
        entry = journal.get(run_id)
        if entry is None or entry.resolution != "active":
            return 0
        journal.resolve(run_id, resolution="operator_acknowledged")
        return 0
    print("Unknown recovery action.", file=sys.stderr)
    return 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Merida API.")
    parser.add_argument("--reload", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    recovery = subparsers.add_parser(
        "recovery", description="Inspect or reconcile local recovery entries."
    )
    recovery.add_argument(
        "action", choices=("inspect", "reconcile", "acknowledge")
    )
    recovery.add_argument("--run-id")
    recovery.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    settings = Settings()

    if args.command == "recovery":
        raise SystemExit(
            run_recovery_command(
                settings,
                args.action,
                run_id=args.run_id,
                confirmed=args.yes,
            )
        )

    if args.reload:
        uvicorn.run(
            "merida_api.main:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=True,
        )
        return

    uvicorn.run(
        create_app(settings, require_dashboard=True),
        host=settings.api_host,
        port=settings.api_port,
        workers=1,
    )


if __name__ == "__main__":
    main()
