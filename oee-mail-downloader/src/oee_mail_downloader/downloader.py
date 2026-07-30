from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from oee_mail_downloader.outlook_client import OutlookClient


def attachment_matches(filename: str, attachment_rule: dict[str, Any]) -> bool:
    normalized = filename.casefold()

    allowed_extensions = {
        extension.casefold()
        for extension in attachment_rule.get(
            "extensions",
            [".xlsx", ".xls", ".xlsm", ".csv"],
        )
    }

    if Path(filename).suffix.casefold() not in allowed_extensions:
        return False

    include = attachment_rule.get("include", [])
    exclude = attachment_rule.get("exclude", [])

    if any(keyword.casefold() in normalized for keyword in exclude):
        return False

    if include and not any(keyword.casefold() in normalized for keyword in include):
        return False

    return True


def get_attachment_rules(rule: dict[str, Any]) -> list[dict[str, Any]]:
    attachments_config = rule.get("attachments", {})

    if isinstance(attachments_config, list):
        return [
            attachment_rule
            for attachment_rule in attachments_config
            if isinstance(attachment_rule, dict)
        ]

    if isinstance(attachments_config, dict):
        return [
            {
                "include": attachments_config.get("include", []),
                "exclude": attachments_config.get("exclude", []),
                "extensions": rule.get(
                    "extensions",
                    [".xlsx", ".xls", ".xlsm", ".csv"],
                ),
                "dataset_name": rule.get("dataset_name", ""),
                "output_folder": rule.get("output_folder", ""),
            }
        ]

    return []


def find_attachment_rule(
    filename: str,
    attachment_rules: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for attachment_rule in attachment_rules:
        if attachment_matches(filename, attachment_rule):
            return attachment_rule
    return None


def build_output_path(
    output_folder: Path,
    received_at: datetime,
    filename: str,
    dataset_name: str = "",
    save_mode: str = "dated_archive",
) -> Path:
    if dataset_name:
        output_stem = dataset_name.strip()
        output_suffix = Path(filename).suffix.lower()
        if Path(output_stem).suffix:
            safe_name = output_stem.replace("/", "_").replace("\\", "_")
        else:
            safe_name = f"{output_stem}{output_suffix}"
    else:
        safe_name = filename.replace("/", "_").replace("\\", "_")

    if save_mode == "replace_latest":
        output_name = safe_name
    else:
        output_name = f"{received_at:%Y-%m-%d}_{safe_name}"

    return output_folder / output_name


def build_state_key(
    rule_name: str,
    entry_id: str,
    attachment_index: int,
    filename: str,
) -> str:
    return f"{rule_name}|{entry_id}|{attachment_index}|{filename}"


def build_dataset_state_key(
    rule_name: str,
    output_folder_name: str,
    dataset_name: str,
) -> str:
    return f"{rule_name}|{output_folder_name}|{dataset_name}"


def get_latest_dataset_state(state: dict[str, Any]) -> dict[str, Any]:
    latest_datasets = state.get("_latest_datasets")
    if isinstance(latest_datasets, dict):
        return latest_datasets

    latest_datasets = {}
    state["_latest_datasets"] = latest_datasets
    return latest_datasets


def parse_state_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def run_rule(
    client: OutlookClient,
    mailbox: str | None,
    rule_name: str,
    rule: dict[str, Any],
    start_at: datetime,
    end_at_exclusive: datetime,
    output_root: Path,
    state: dict[str, Any],
    dry_run: bool,
    force: bool,
) -> tuple[int, int]:
    sender = str(rule.get("sender", "")).casefold()
    subject = str(rule.get("subject", "")).casefold()
    default_output_folder = str(rule.get("output_folder", rule_name))
    attachment_rules = get_attachment_rules(rule)
    latest_dataset_state = get_latest_dataset_state(state)
    processed_replace_latest: set[str] = set()

    inbox = client.get_inbox(mailbox)
    matched_emails = 0
    downloaded_files = 0

    for message in client.iter_messages(
        inbox,
        start_at=start_at,
        end_at_exclusive=end_at_exclusive,
    ):
        sender_values = [
            value.casefold()
            for value in client.get_sender_values(message)
        ]
        message_subject = str(getattr(message, "Subject", "")).casefold()

        if sender and not any(sender in value for value in sender_values):
            continue

        if subject and subject not in message_subject:
            continue

        matched_emails += 1
        received_at = client.to_local_datetime(message.ReceivedTime)
        entry_id = str(getattr(message, "EntryID", ""))

        logging.info(
            "[MAIL] %s | %s",
            received_at.strftime("%Y-%m-%d %H:%M:%S"),
            getattr(message, "Subject", ""),
        )

        for index in range(1, message.Attachments.Count + 1):
            attachment = message.Attachments.Item(index)
            filename = str(attachment.FileName)

            attachment_rule = find_attachment_rule(filename, attachment_rules)

            if attachment_rule is None:
                logging.info("[SKIP] %s", filename)
                continue

            output_folder_name = str(
                attachment_rule.get("output_folder", default_output_folder)
            )
            output_folder = output_root / output_folder_name
            output_folder.mkdir(parents=True, exist_ok=True)
            dataset_name = str(attachment_rule.get("dataset_name", "")).strip()
            save_mode = str(
                attachment_rule.get(
                    "save_mode",
                    rule.get("save_mode", "dated_archive"),
                )
            ).strip() or "dated_archive"

            output_path = build_output_path(
                output_folder,
                received_at,
                filename,
                dataset_name=dataset_name,
                save_mode=save_mode,
            )

            if save_mode == "replace_latest":
                dataset_state_key = build_dataset_state_key(
                    rule_name,
                    output_folder_name,
                    dataset_name or filename,
                )

                if dataset_state_key in processed_replace_latest:
                    logging.info("[SKIP-OLDER] %s", filename)
                    continue

                processed_replace_latest.add(dataset_state_key)

                previous_dataset_state = latest_dataset_state.get(
                    dataset_state_key,
                    {},
                )
                previous_received_at = parse_state_datetime(
                    previous_dataset_state.get("received_at")
                )

                if (
                    not force
                    and previous_received_at is not None
                    and previous_received_at >= received_at
                    and output_path.exists()
                ):
                    logging.info(
                        "[SKIP-LATEST] %s -> current latest already saved",
                        filename,
                    )
                    continue
            else:
                state_key = build_state_key(rule_name, entry_id, index, filename)

                if not force and state_key in state and output_path.exists():
                    logging.info("[SKIP-DUPLICATE] %s", filename)
                    continue

            if dry_run:
                logging.info("[DRY-RUN] %s -> %s", filename, output_path)
                continue

            attachment.SaveAsFile(str(output_path.resolve()))

            saved_at = datetime.now().isoformat(timespec="seconds")

            if save_mode == "replace_latest":
                latest_dataset_state[dataset_state_key] = {
                    "rule": rule_name,
                    "downloaded_at": saved_at,
                    "received_at": received_at.isoformat(timespec="seconds"),
                    "filename": filename,
                    "dataset_name": dataset_name,
                    "save_mode": save_mode,
                    "output_path": str(output_path),
                    "entry_id": entry_id,
                    "attachment_index": index,
                }
            else:
                state[state_key] = {
                    "rule": rule_name,
                    "downloaded_at": saved_at,
                    "received_at": received_at.isoformat(timespec="seconds"),
                    "filename": filename,
                    "dataset_name": dataset_name,
                    "save_mode": save_mode,
                    "output_path": str(output_path),
                }

            downloaded_files += 1
            logging.info("[SAVED] %s", output_path)

    return matched_emails, downloaded_files
