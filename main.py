from pathlib import Path
import sys

PACKAGE_SRC = Path(__file__).resolve().parent / "oee-ingestion" / "src"
if str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

from oee_ingestion.main import main


if __name__ == "__main__":
    main()
