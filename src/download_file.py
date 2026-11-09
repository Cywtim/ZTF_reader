"""Download ZTF products for requests that have left the pending queue."""

import argparse
from datetime import datetime
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

import requests
from dotenv import dotenv_values

from config import DOWNLOAD_DIR, ENV_FILE, HOST, LOG_DIR, ZTF_AUTH_USER


PENDING_COUNT = re.compile(r"^(\d+|no) records? returned\b", re.IGNORECASE)
PRODUCT_URL = re.compile(
    rf"{re.escape(HOST)}/ztf/ops/forcedphot/lc/batchfp/"
    r"(?:[A-Za-z0-9_-]+/)+(?P<filename>batchfp_req(?P<id>\d+)_lc\.txt)"
)


def job_rows(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        fields = [value.strip() for value in line.split("|")]
        if len(fields) in (11, 12) and fields[0].isascii() and fields[0].isdigit():
            rows.append(fields)
    return rows


def pending_snapshots(log_dir: Path) -> dict[datetime, set[int]]:
    snapshots = {}
    for pattern in ("pending_*.log", "check_*.log"):
        for path in log_dir.glob(pattern):
            lines = path.read_text(encoding="utf-8").splitlines()
            if lines[1:3] != ["Mode: Pending jobs", "HTTP status: 200"]:
                continue
            match = next((match for line in lines[3:] if (match := PENDING_COUNT.match(line))), None)
            if not match:
                continue
            request_ids = {int(row[0]) for row in job_rows(lines[3:])}
            count = 0 if match[1].lower() == "no" else int(match[1])
            if len(request_ids) != count:
                continue
            prefix = "Query started (UTC): "
            if not lines[0].startswith(prefix):
                continue
            try:
                timestamp = datetime.fromisoformat(lines[0].removeprefix(prefix))
            except ValueError:
                continue
            if timestamp.tzinfo is not None:
                snapshots[timestamp] = request_ids
    return snapshots


def finished_products(log_dir: Path, request_ids: set[int]) -> dict[int, str]:
    products = {}
    for path in sorted(log_dir.glob("finished_*.log"), reverse=True):
        lines = path.read_text(encoding="utf-8").splitlines()
        rows = job_rows(lines)
        if len(lines) < 3 or lines[2] != f"Finished jobs returned: {len(rows)}":
            continue
        for row in rows:
            request_id = int(row[0])
            if request_id not in request_ids or row[-1] != "finished":
                continue
            product = PRODUCT_URL.fullmatch(row[10])
            if product and int(product["id"]) == request_id:
                products.setdefault(request_id, row[10])
    return products


def download_product(session: requests.Session, url: str, destination: Path) -> bool:
    with session.get(url, timeout=(15, 120), stream=True, allow_redirects=False) as response:
        if response.status_code != 200:
            raise RuntimeError(f"IPAC returned HTTP {response.status_code}")
        temporary = None
        try:
            with NamedTemporaryFile(
                dir=destination.parent, prefix=".ztf_", suffix=".part", delete=False
            ) as output:
                temporary = Path(output.name)
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    output.write(chunk)
            with temporary.open("rb") as source:
                header = source.read(8192)
            if b"# Requested input R.A. =" not in header or b"# Requested input Dec. =" not in header:
                raise RuntimeError("IPAC response did not contain a ZTF light-curve header")
            try:
                destination.hardlink_to(temporary)
            except FileExistsError:
                return False
            return True
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="List eligible files without downloading")
    args = parser.parse_args()

    snapshots = pending_snapshots(LOG_DIR)
    if not snapshots:
        print("No valid pending snapshots. Run python3 -m src.checking_ztf --pending first.")
        return
    if len(snapshots) == 1:
        print("Only one valid pending snapshot. It is the baseline. Check pending jobs again later.")
        return

    latest = snapshots[max(snapshots)]
    disappeared = set().union(*snapshots.values()) - latest
    if not disappeared:
        print("No previously pending requests have left the latest pending snapshot.")
        return

    products = finished_products(LOG_DIR, disappeared)
    unconfirmed = disappeared - products.keys()
    if unconfirmed:
        print(f"{len(unconfirmed)} request(s) left pending without a confirmed product link in the finished logs.")

    eligible = []
    for request_id, url in sorted(products.items()):
        destination = DOWNLOAD_DIR / url.rsplit("/", 1)[-1]
        if not destination.exists():
            eligible.append((request_id, url, destination))
    print(f"{len(eligible)} new file(s) eligible for download.")
    if args.dry_run:
        for request_id, _, destination in eligible:
            print(f"{request_id}: {destination.name}")
    if args.dry_run or not eligible:
        return

    password = dotenv_values(ENV_FILE, interpolate=False).get("ZTF_SHARED_PASSWORD")
    if not password:
        parser.error(f"Fill in ZTF_SHARED_PASSWORD in {ENV_FILE}.")
    DOWNLOAD_DIR.mkdir(exist_ok=True, mode=0o700)
    failed = False
    with requests.Session() as session:
        session.auth = (ZTF_AUTH_USER, password)
        for request_id, url, destination in eligible:
            try:
                if download_product(session, url, destination):
                    print(f"{request_id}: saved {destination}")
                else:
                    print(f"{request_id}: already exists")
            except (requests.RequestException, OSError, RuntimeError) as error:
                message = str(error) if isinstance(error, RuntimeError) else type(error).__name__
                print(f"{request_id}: download failed ({message})")
                failed = True
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
