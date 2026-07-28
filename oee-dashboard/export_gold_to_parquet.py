from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "oee.db"
EXPORT_DIR = PROJECT_ROOT / "data" / "exports" / "powerbi"

GOLD_TABLES = [
    "gld_date_dim",
    "gld_machine_dim",
    "gld_beam_plan_dim",
    "gld_production_daily_fact",
    "gld_machine_status_daily_fact",
]


def export_table(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    export_dir: Path,
) -> tuple[str, int, Path]:
    output_path = export_dir / f"{table_name}.parquet"
    if output_path.exists():
        output_path.unlink()

    quoted_table = '"' + table_name.replace('"', '""') + '"'
    conn.execute(
        f"COPY (SELECT * FROM {quoted_table}) "
        f"TO ? (FORMAT PARQUET)",
        [str(output_path)],
    )
    row_count = conn.execute(
        f"SELECT COUNT(*) FROM {quoted_table}"
    ).fetchone()[0]
    return table_name, row_count, output_path


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        for table_name in GOLD_TABLES:
            exported_table, row_count, output_path = export_table(
                conn=conn,
                table_name=table_name,
                export_dir=EXPORT_DIR,
            )
            print(
                f"Exported {exported_table} "
                f"({row_count:,} rows) -> {output_path}"
            )


if __name__ == "__main__":
    main()
