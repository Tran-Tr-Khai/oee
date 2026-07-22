from typing import Any
import re
import pandas as pd

CLEAN_CHARS_REGEX = re.compile(r"[()]+")
SPLIT_CHARS_REGEX = re.compile(r"[\s/\\\-.]+")
MULTIPLE_UNDERSCORES_REGEX = re.compile(r"_+")

def normalize_column_name(column: Any) -> str:
    if isinstance(column, tuple):
        parts = [
            str(raw).strip()
            for raw in column
            if pd.notna(raw) and str(raw).strip() and not str(raw).startswith("Unnamed")    
        ]
        name = "_".join(parts)
    else: 
        name = str(column).strip()

    name = CLEAN_CHARS_REGEX.sub("", name)
    name = SPLIT_CHARS_REGEX.sub("_", name)
    name = MULTIPLE_UNDERSCORES_REGEX.sub("_", name)
    return name.strip("_")

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame: 
    columns = []
    seen: dict[str, int] = {}

    for col in df.columns: 
        name = normalize_column_name(col)
        if not name: 
            name = "unnamed"
        
        count = seen.get(name, 0)
        seen[name] = count
        columns.append(name if count == 0 else f"{name}_{count + 1}")
    
    df.columns = columns
    return df


def normalize_machine_no(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .replace("", pd.NA)
    )

