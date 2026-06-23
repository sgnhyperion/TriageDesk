# Load backend/.env on import so env vars are available no matter the CWD.
# Wrapped in try/except so the stub still runs before deps are installed.
try:
    from pathlib import Path
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass
