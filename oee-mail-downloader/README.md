# OEE Mail Downloader

Read Outlook Classic and save the right attachments to the shared raw-data area for the workspace.

## Structure

```text
oee-mail-downloader/
|-- main.py
|-- pyproject.toml
|-- README.md
|-- config.yaml
|-- state.json
|-- run_daily.ps1
|-- logs/
`-- src/
    `-- oee_mail_downloader/
        |-- __init__.py
        |-- __main__.py
        |-- cli.py
        |-- config.py
        |-- downloader.py
        `-- outlook_client.py
```

## Output

The default config writes files to:

```text
../data/raw
```

That resolves to the shared workspace data folder:

```text
oee/data/raw
```

This keeps `oee-mail-downloader` and `oee-ingestion` on the same raw-data source.
The downloader writes files directly into this folder, without a `weaving`
subfolder.

## Save modes

Each attachment rule can set:

- `dataset_name`
- `save_mode`

Supported save modes:

- `replace_latest`: pick the newest matched file in the date range and keep one snapshot file
- `dated_archive`: keep one file per day

Examples:

```text
textile_days.xlsx
2026-07-29_start_beam.xlsx
```

Use `replace_latest` for cumulative files such as `textile_days`.

Use `dated_archive` for daily files such as `start_beam`.

For `replace_latest`, the downloader:

- scans all matched emails in the date range
- keeps only the newest matched attachment for that dataset
- skips download if `state.json` already knows the same or newer file

This keeps `oee-ingestion` compatible with patterns like:

- `*textile_days*`
- `*start_beam*`

## Requirements

- Windows
- Microsoft Outlook Classic is signed in
- Python 3.11+
- uv

## Setup

```powershell
uv sync
```

You do not need to activate `.venv`.

## Check before download

```powershell
uv run python main.py `
  --rule weaving `
  --start-date 2026-07-01 `
  --end-date 2026-07-28 `
  --dry-run
```

## Backfill

```powershell
uv run python main.py `
  --rule weaving `
  --start-date 2026-06-01 `
  --end-date 2026-07-28
```

## Run every day

```powershell
uv run python main.py --today
```

Or run:

```powershell
.\run_daily.ps1
```

## Avoid duplicate download

Saved attachments are stored in `state.json`. To download again:

```powershell
uv run python main.py --today --force
```

## Config example

```yaml
output_root: ../data/raw

rules:
  weaving:
    output_folder: ""
    attachments:
      - dataset_name: textile_days
        save_mode: replace_latest
        include:
          - SẢN LƯỢNG DỆT
        exclude:
          - Consumable

      - dataset_name: start_beam
        save_mode: dated_archive
        include:
          - 호기별 상하대 일정
```
