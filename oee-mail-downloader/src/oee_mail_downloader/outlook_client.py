from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any

import win32com.client


OL_FOLDER_INBOX = 6
OL_MAIL_ITEM = 43


class OutlookClient:
    def __init__(self) -> None:
        outlook = win32com.client.Dispatch("Outlook.Application")
        self.namespace = outlook.GetNamespace("MAPI")

    def get_inbox(self, mailbox: str | None) -> Any:
        if not mailbox:
            return self.namespace.GetDefaultFolder(OL_FOLDER_INBOX)

        expected = mailbox.casefold()

        for index in range(1, self.namespace.Stores.Count + 1):
            store = self.namespace.Stores.Item(index)
            display_name = str(getattr(store, "DisplayName", "")).casefold()

            if expected in display_name or display_name in expected:
                return store.GetDefaultFolder(OL_FOLDER_INBOX)

        available = [
            str(self.namespace.Stores.Item(index).DisplayName)
            for index in range(1, self.namespace.Stores.Count + 1)
        ]

        raise RuntimeError(
            f"Mailbox not found: {mailbox!r}. Available mailboxes: {available}"
        )

    def iter_messages(
        self,
        inbox: Any,
        start_at: datetime,
        end_at_exclusive: datetime,
    ) -> Iterator[Any]:
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)

        for index in range(1, items.Count + 1):
            item = items.Item(index)

            if getattr(item, "Class", None) != OL_MAIL_ITEM:
                continue

            received_at = self.to_local_datetime(item.ReceivedTime)

            if received_at < start_at:
                break

            if received_at >= end_at_exclusive:
                continue

            yield item

    @staticmethod
    def to_local_datetime(value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone().replace(tzinfo=None)
        return value

    @staticmethod
    def get_sender_values(message: Any) -> tuple[str, ...]:
        values: list[str] = []

        for attribute in ("SenderName", "SenderEmailAddress"):
            try:
                value = getattr(message, attribute, None)
                if value:
                    values.append(str(value))
            except Exception:
                pass

        try:
            sender = message.Sender
            exchange_user = sender.GetExchangeUser() if sender else None

            if exchange_user and exchange_user.PrimarySmtpAddress:
                values.append(str(exchange_user.PrimarySmtpAddress))
        except Exception:
            pass

        return tuple(values)
