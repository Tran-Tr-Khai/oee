from datetime import datetime
import logging
import re

import pandas as pd

from oee_ingestion.normalization import (
    normalize_columns,
    normalize_machine_no,
)


KOREAN_DATE_REGEX = re.compile(r"(\d{1,2})월(\d{1,2})일")

TEXTILE_CURRENT_MONTH_START_COL_IDX = 5
TEXTILE_DATA_START_ROW_IDX = 4
TEXTILE_MACHINE_COL_IDX = 0


def resolve_production_year(
    sheet_year: int,
    sheet_month: int,
    production_month: int,
) -> int:
    """Resolve the production year when a sheet crosses a year boundary."""
    month_difference = production_month - sheet_month

    if month_difference >= 6:
        return sheet_year - 1

    if month_difference <= -6:
        return sheet_year + 1

    return sheet_year


def normalize_textile_merge_keys(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Normalize keys used to merge LOT and production data."""
    df = df.copy()

    df["machine_no"] = normalize_machine_no(df["machine_no"])
    df["prod_date"] = pd.to_datetime(
        df["prod_date"],
        errors="coerce",
    )

    return df.dropna(
        subset=["machine_no", "prod_date"],
    )


def should_skip_sheet(sheet_name: str) -> bool:
    """Return True for summary sheets that should not be ingested."""
    sheet_key = sheet_name.strip().lower()

    return (
        sheet_key.startswith("total")
        or sheet_key == "kangatang"
    )


def extract_lot_table(
    df: pd.DataFrame,
    sheet_name: str,
) -> tuple[pd.DataFrame, int | None, int | None]:
    """Extract machine, production date and LOT number."""
    lot_headers = df.iloc[3].values

    lot_cols: list[int] = []
    lot_dates: list[pd.Timestamp] = []

    sheet_year: int | None = None
    sheet_month: int | None = None

    for col_idx, value in enumerate(lot_headers):
        if pd.isna(value):
            continue

        lot_date = pd.to_datetime(
            value,
            errors="coerce",
        )

        if pd.isna(lot_date):
            continue

        lot_cols.append(col_idx)
        lot_dates.append(lot_date)

        if (
            sheet_year is None
            and col_idx >= TEXTILE_CURRENT_MONTH_START_COL_IDX
        ):
            sheet_year = lot_date.year
            sheet_month = lot_date.month

    if not lot_cols:
        logging.warning(
            "Skipping sheet %s: no LOT date columns found",
            sheet_name,
        )
        return pd.DataFrame(), None, None

    if sheet_year is None or sheet_month is None:
        logging.warning(
            "Skipping sheet %s: no current-month LOT date found "
            "from column %d onwards",
            sheet_name,
            TEXTILE_CURRENT_MONTH_START_COL_IDX,
        )
        return pd.DataFrame(), None, None

    df_lot = df.iloc[
        TEXTILE_DATA_START_ROW_IDX:,
        [TEXTILE_MACHINE_COL_IDX, *lot_cols],
    ].copy()

    df_lot.columns = [
        "machine_no",
        *lot_dates,
    ]

    df_lot = df_lot.dropna(
        subset=["machine_no"],
    )

    df_lot = df_lot.melt(
        id_vars=["machine_no"],
        var_name="prod_date",
        value_name="lot_no",
    )

    df_lot["lot_no"] = (
        df_lot["lot_no"]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
    )

    df_lot = df_lot.dropna(
        subset=["lot_no"],
    )

    df_lot = normalize_textile_merge_keys(df_lot)

    if df_lot.empty:
        logging.warning(
            "Skipping sheet %s: LOT table is empty after cleaning",
            sheet_name,
        )

    return df_lot, sheet_year, sheet_month


def parse_production_date(
    date_header: object,
    sheet_year: int,
    sheet_month: int,
    sheet_name: str,
    output_col_idx: int,
) -> pd.Timestamp | None:
    """Parse a production date from an Excel or Korean date header."""
    if isinstance(date_header, (pd.Timestamp, datetime)):
        production_month = date_header.month
        production_day = date_header.day
        date_description = str(date_header)
    else:
        date_description = (
            ""
            if pd.isna(date_header)
            else str(date_header).replace(" ", "")
        )

        date_match = KOREAN_DATE_REGEX.search(date_description)

        if not date_match:
            logging.warning(
                "Could not extract production date from %s "
                "in sheet %s, column %d",
                date_header,
                sheet_name,
                output_col_idx,
            )
            return None

        production_month, production_day = map(
            int,
            date_match.groups(),
        )

    production_year = resolve_production_year(
        sheet_year=sheet_year,
        sheet_month=sheet_month,
        production_month=production_month,
    )

    try:
        return pd.Timestamp(
            year=production_year,
            month=production_month,
            day=production_day,
        )
    except ValueError:
        logging.warning(
            "Skipping invalid production date %s in sheet %s",
            date_description,
            sheet_name,
        )
        return None


def extract_production_table(
    df: pd.DataFrame,
    sheet_name: str,
    sheet_year: int,
    sheet_month: int,
) -> pd.DataFrame:
    """Extract daily production measurements by machine."""
    production_headers = df.iloc[2].values
    source_rows = df.iloc[TEXTILE_DATA_START_ROW_IDX:]

    valid_machine_mask = source_rows.iloc[
        :,
        TEXTILE_MACHINE_COL_IDX,
    ].notna()

    valid_rows = source_rows.loc[
        valid_machine_mask
    ]

    if valid_rows.empty:
        logging.warning(
            "Skipping sheet %s: no machine rows found",
            sheet_name,
        )
        return pd.DataFrame()

    machines = normalize_machine_no(
        valid_rows.iloc[:, TEXTILE_MACHINE_COL_IDX]
    ).to_numpy()

    production_chunks: list[pd.DataFrame] = []

    for output_col_idx, header_value in enumerate(
        production_headers
    ):
        header_text = (
            ""
            if pd.isna(header_value)
            else str(header_value).replace(" ", "")
        )

        if "생산량" not in header_text:
            continue

        if output_col_idx < 2:
            logging.warning(
                "Skipping invalid production column %d "
                "in sheet %s",
                output_col_idx,
                sheet_name,
            )
            continue

        meter_reading_col_idx = output_col_idx - 2
        cut_length_col_idx = output_col_idx - 1

        date_header = production_headers[
            meter_reading_col_idx
        ]

        prod_date = parse_production_date(
            date_header=date_header,
            sheet_year=sheet_year,
            sheet_month=sheet_month,
            sheet_name=sheet_name,
            output_col_idx=output_col_idx,
        )

        if prod_date is None:
            continue

        production_chunks.append(
            pd.DataFrame(
                {
                    "machine_no": machines,
                    "prod_date": prod_date,
                    "meter_reading_m": valid_rows.iloc[
                        :, meter_reading_col_idx
                    ].to_numpy(),
                    "cut_length_m": valid_rows.iloc[
                        :, cut_length_col_idx
                    ].to_numpy(),
                    "prod_output_m": valid_rows.iloc[
                        :, output_col_idx
                    ].to_numpy(),
                }
            )
        )

    if not production_chunks:
        logging.warning(
            "Skipping sheet %s: no production columns found",
            sheet_name,
        )
        return pd.DataFrame()

    df_prod = pd.concat(
        production_chunks,
        ignore_index=True,
    )

    df_prod = normalize_textile_merge_keys(df_prod)

    if df_prod.empty:
        logging.warning(
            "Skipping sheet %s: production table is empty "
            "after cleaning",
            sheet_name,
        )

    return df_prod


def merge_textile_tables(
    df_lot: pd.DataFrame,
    df_prod: pd.DataFrame,
) -> pd.DataFrame:
    """Merge LOT and production tables into the final dataset."""
    df_final = pd.merge(
        df_lot,
        df_prod,
        on=["machine_no", "prod_date"],
        how="outer",
        validate="one_to_one",
    )

    df_final = df_final.dropna(
        subset=[
            "lot_no",
            "meter_reading_m",
            "cut_length_m",
            "prod_output_m",
        ],
        how="all",
    )

    numeric_cols = [
        "meter_reading_m",
        "cut_length_m",
        "prod_output_m",
    ]

    for col in numeric_cols:
        df_final[col] = pd.to_numeric(
            df_final[col],
            errors="coerce",
        )

    df_final = df_final.sort_values(
        ["machine_no", "prod_date"],
        kind="stable",
    )

    return normalize_columns(
        df_final
    ).reset_index(drop=True)


def extract_textile_days(
    workbook: pd.ExcelFile,
    sheet_name: str,
) -> pd.DataFrame:
    """Extract daily textile production data from one worksheet."""
    if should_skip_sheet(sheet_name):
        return pd.DataFrame()

    df = pd.read_excel(
        workbook,
        sheet_name=sheet_name,
        header=None,
    )

    if len(df) < 5:
        logging.warning(
            "Skipping sheet %s: expected at least 5 rows, found %d",
            sheet_name,
            len(df),
        )
        return pd.DataFrame()

    df_lot, sheet_year, sheet_month = extract_lot_table(
        df=df,
        sheet_name=sheet_name,
    )

    if (
        df_lot.empty
        or sheet_year is None
        or sheet_month is None
    ):
        return pd.DataFrame()

    df_prod = extract_production_table(
        df=df,
        sheet_name=sheet_name,
        sheet_year=sheet_year,
        sheet_month=sheet_month,
    )

    if df_prod.empty:
        return pd.DataFrame()

    return merge_textile_tables(
        df_lot=df_lot,
        df_prod=df_prod,
    )