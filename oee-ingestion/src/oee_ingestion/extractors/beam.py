import pandas as pd
from oee_ingestion.normalization import normalize_columns

START_BEAM_COLUMN_MAP = {
    "호기_số_máy": "machine_no",
    "model": "model",
    "품목_loại_hàng": "item_type",
    "unit": "unit",
    "상대일_ngày_lên_beam": "beam_start_date",
    "po": "po",
    "order": "order_no",
    "lot_no": "lot_no",
    "total_yarn": "total_yarn",
    "b_m_no": "beam_no",
    "length": "length",
    "pro": "planned_output",
    "대차_chênh_lệch": "output_gap",
    "%": "output_rate",
    "하대예정일_ngày_dự_kiến_hết_beam": "expected_beam_end_at",
    "제직기간일_thời_gian_dệt": "weaving_days",
    "1일생산량mts_số_mts_dệt_mỗi_ngày": "daily_output_mts",
}

START_BEAM_DATE_COLS = [
    "beam_start_date", 
    "expected_beam_end_at"
]

START_BEAM_NUMERIC_COLS = [
    "machine_no",
    "total_yarn",
    "length",
    "planned_output",
    "output_gap",
    "output_rate",
    "weaving_days",
    "daily_output_mts",
]

def extract_complete_beam(workbook: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(workbook, sheet_name=sheet_name, header=[0, 1])
    df = normalize_columns(df)
    return df.dropna(axis=0, how="all").dropna(axis=1, how="all")

def extract_start_beam(workbook: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    raw_head = pd.read_excel(workbook, sheet_name=sheet_name, header=None, nrows=3)
    if raw_head.empty:
        return pd.DataFrame()

    updated_at = None
    for _, row in raw_head.iterrows():
        dates = pd.to_datetime(row.dropna(), errors="coerce").dropna()
        if not dates.empty:
            updated_at = dates.iloc[-1]
            break

    df = pd.read_excel(workbook, sheet_name=sheet_name, header=2)
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

    if df.empty:
        return pd.DataFrame()

    df = normalize_columns(df).rename(columns=START_BEAM_COLUMN_MAP)
    df["_updated_at"] = updated_at
    df["_excel_row_number"] = df.index + 4

    for col in START_BEAM_DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in START_BEAM_NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.reset_index(drop=True)