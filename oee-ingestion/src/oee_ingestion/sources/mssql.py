from datetime import datetime, timezone
from urllib.parse import quote_plus

import pandas as pd

from oee_ingestion.config import MssqlConfig


def build_odbc_connection_string(
    config: MssqlConfig,
) -> str:
    trust_flag = "yes" if config.trust_server_certificate else "no"
    return (
        f"DRIVER={{{config.driver}}};"
        f"SERVER={config.server};"
        f"DATABASE={config.database};"
        f"UID={config.username};"
        f"PWD={config.password};"
        f"TrustServerCertificate={trust_flag};"
    )


def read_sql_server_table(
    query: str,
    connection_string: str,
) -> pd.DataFrame:
    return pd.read_sql(
        sql=query,
        con=f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}",
    )


def read_machine_status(
    config: MssqlConfig,
) -> pd.DataFrame:
    query = """
        SELECT
            [id],
            [machine_id],
            [status],
            [timestamp]
        FROM [ESP32].[dbo].[ws2_working_status]
    """
    df = read_sql_server_table(
        query=query,
        connection_string=build_odbc_connection_string(config),
    )
    df["_ingested_at"] = datetime.now(timezone.utc)
    return df
