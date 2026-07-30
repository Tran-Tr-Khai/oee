from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path

from oee_mail_downloader.config import (
    DEFAULT_CONFIG,
    DEFAULT_LOG,
    DEFAULT_STATE,
    PROJECT_ROOT,
    load_config,
    load_state,
    resolve_output_root,
    save_state,
)
from oee_mail_downloader.downloader import run_rule
from oee_mail_downloader.outlook_client import OutlookClient

def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download Outlook attachments with YAML config."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--today",
        action="store_true",
        help="Only download emails from today.",
    )
    group.add_argument(
        "--start-date",
        type=parse_date,
        help="Start date in YYYY-MM-DD.",
    )

    parser.add_argument(
        "--end-date",
        type=parse_date,
        help="End date. If empty, use today.",
    )
    parser.add_argument(
        "--rule",
        help="Run one rule only, for example: weaving.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show matched files only. Do not download.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Download again even if state.json has it.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to config.yaml.",
    )

    return parser


def setup_logging() -> None:
    DEFAULT_LOG.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(DEFAULT_LOG, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def resolve_date_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    today = date.today()

    if args.today:
        start_date = today
        end_date = today
    else:
        start_date = args.start_date
        end_date = args.end_date or today

    if end_date < start_date:
        raise ValueError("--end-date cannot be earlier than --start-date.")

    start_at = datetime.combine(start_date, time.min)
    end_at_exclusive = datetime.combine(end_date + timedelta(days=1), time.min)

    return start_at, end_at_exclusive


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()

    try:
        config = load_config(args.config)
        state = load_state(DEFAULT_STATE)
        start_at, end_at_exclusive = resolve_date_range(args)

        output_root = resolve_output_root(PROJECT_ROOT, config)
        mailbox = config.get("mailbox")
        rules = config["rules"]

        client = OutlookClient()

        selected_rules = {
            name: rule
            for name, rule in rules.items()
            if rule.get("enabled", True)
            and (args.rule is None or name == args.rule)
        }

        if args.rule and args.rule not in selected_rules:
            raise ValueError(f"Enabled rule not found: {args.rule}")

        total_emails = 0
        total_files = 0

        for rule_name, rule in selected_rules.items():
            logging.info("Start rule: %s", rule_name)

            matched_emails, downloaded_files = run_rule(
                client=client,
                mailbox=mailbox,
                rule_name=rule_name,
                rule=rule,
                start_at=start_at,
                end_at_exclusive=end_at_exclusive,
                output_root=output_root,
                state=state,
                dry_run=args.dry_run,
                force=args.force,
            )

            total_emails += matched_emails
            total_files += downloaded_files

            logging.info(
                "Done rule=%s | emails=%s | files=%s",
                rule_name,
                matched_emails,
                downloaded_files,
            )

        if not args.dry_run:
            save_state(DEFAULT_STATE, state)

        logging.info("Done all | emails=%s | files=%s", total_emails, total_files)
        return 0

    except Exception as exc:
        logging.exception("Pipeline error: %s", exc)
        return 1
