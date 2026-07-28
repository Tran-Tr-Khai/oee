from pathlib import Path
import sys

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQL_PATH = PROJECT_ROOT / "oee-quality" / "checks" / "raw" / "raw_quality_checks.sql"
DEFAULT_DB_PATH = PROJECT_ROOT / "db" / "oee.db"
SQL_PRESETS = {
    "0": PROJECT_ROOT / "oee-quality" / "checks" / "raw" / "raw_quality_checks.sql",
    "1": PROJECT_ROOT / "oee-quality" / "checks" / "silver" / "silver_quality_checks.sql",
    "2": PROJECT_ROOT / "oee-quality" / "checks" / "gold" / "gold_quality_checks.sql",
}


def resolve_path(raw_path: str, fallback_base: Path) -> Path:
    preset_path = SQL_PRESETS.get(raw_path)
    if preset_path is not None:
        return preset_path

    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (fallback_base / path).resolve()


def main() -> None:
    sql_path = (
        resolve_path(sys.argv[1], PROJECT_ROOT)
        if len(sys.argv) > 1
        else DEFAULT_SQL_PATH
    )
    db_path = (
        resolve_path(sys.argv[2], PROJECT_ROOT)
        if len(sys.argv) > 2
        else DEFAULT_DB_PATH
    )

    sql_text = sql_path.read_text(encoding="utf-8")
    statements = [
        statement.strip()
        for statement in sql_text.split(";")
        if statement.strip()
    ]

    con = duckdb.connect(str(db_path), read_only=True)

    try:
        for index, statement in enumerate(statements, start=1):
            print(f"\n== Statement {index} ==")
            print(statement)
            result = con.execute(statement).fetchdf()
            print(result.to_string(index=False))
    finally:
        con.close()


if __name__ == "__main__":
    main()
