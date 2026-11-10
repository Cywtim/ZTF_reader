"""Shared paths and service settings for the ZTF tools."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
ENV_FILE = ROOT / ".env"
JOB_DIR = ROOT / "job"
LOG_DIR = ROOT / "log"
DOWNLOAD_DIR = ROOT / "download"
CSV_DIR = ROOT / "csv"
FLUX_DIR = ROOT / "flux"

HOST = "https://ztfweb.ipac.caltech.edu"
SUBMIT_URL = HOST + "/cgi-bin/batchfp.py/submit"
STATUS_URL = HOST + "/cgi-bin/getBatchForcedPhotometryRequests.cgi"
ZTF_AUTH_USER = "ztffps"
CREDENTIAL_KEYS = ("ZTF_EMAIL", "ZTF_USERPASS", "ZTF_SHARED_PASSWORD")
