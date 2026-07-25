from pathlib import Path
import sys

import duckdb


DEFAULT_SQL_PATH = Path("test.sql")
DEFAULT_DB_PATH = Path("db/oee.db")


def main() -> None:
    sql_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SQL_PATH
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB_PATH

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
