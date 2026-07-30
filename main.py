from pathlib import Path
import runpy

INGESTION_MAIN = Path(__file__).resolve().parent / "oee-ingestion" / "ingest.py"


if __name__ == "__main__":
    runpy.run_path(str(INGESTION_MAIN), run_name="__main__")
