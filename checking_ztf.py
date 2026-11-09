"""Check IPAC ZTF batch forced-photometry requests."""

import argparse
from datetime import datetime, timezone
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote, quote_plus
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values


HOST = "https://ztfweb.ipac.caltech.edu"
STATUS_URL = HOST + "/cgi-bin/getBatchForcedPhotometryRequests.cgi"
ENV_FILE = Path(__file__).resolve().with_name(".env")
LOG_DIR = ENV_FILE.parent / "log"
PRODUCT_PATH = re.compile(r"/ztf/ops/[\w./-]+?_lc\.txt\b")
JOB_COLUMNS = (
    "reqid", "ra", "dec", "startjd", "endjd", "created", "started",
    "ended", "machine", "exitcode", "lightcurve",
)
MISSING_TIMESTAMPS = {"", "-", "none", "null"}
IPAC_TIMEZONE = ZoneInfo("America/Los_Angeles")
STATE_PRIORITY = {"pending": 2, "running": 1, "finished": 0}


def timestamp_utc(value: str) -> str:
    if value.lower() in MISSING_TIMESTAMPS:
        return value
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        return f"{value} (UTC unresolved)"
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=IPAC_TIMEZONE)
        if timestamp.utcoffset() != timestamp.replace(fold=1).utcoffset():
            return f"{value} (UTC unresolved at Pacific DST transition)"
    return timestamp.astimezone(timezone.utc).isoformat(sep=" ").replace("+00:00", "Z")


def format_reports(html: str) -> tuple[str, str]:
    page = BeautifulSoup(html, "html.parser")
    for element in page.select("script, style, input, select, textarea"):
        element.decompose()
    job_table = None
    job_rows = []
    job_entries = []
    finished_entries = []
    job_header = ""
    for row in page.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if cells and not row.find("tr"):
            values = [cell.get_text(" ", strip=True) for cell in cells]
            table = row.find_parent("table")
            if tuple(value.lower() for value in values) == JOB_COLUMNS:
                job_table = table
                values[5:8] = [f"{value} (UTC)" for value in values[5:8]]
                values.append("processing state")
                job_header = " | ".join(values)
            elif (
                job_table is not None
                and table is job_table
                and len(values) == len(JOB_COLUMNS)
                and values[0].isdigit()
            ):
                started, ended = values[6].lower(), values[7].lower()
                state = "pending"
                if ended not in MISSING_TIMESTAMPS:
                    state = "finished"
                elif started not in MISSING_TIMESTAMPS:
                    state = "running"
                values[5:8] = [timestamp_utc(value) for value in values[5:8]]
                values.append(state)
                created = values[5].removesuffix("Z") if values[5].endswith("Z") else ""
                job_rows.append(row)
                job_entries.append((STATE_PRIORITY[state], created, " | ".join(values)))
                if state == "finished":
                    ended_utc = values[7].removesuffix("Z") if values[7].endswith("Z") else ""
                    product = PRODUCT_PATH.search(str(cells[-1]))
                    if product:
                        values[-2] = HOST + product[0]
                    finished_entries.append((ended_utc, " | ".join(values)))
                continue
            row.replace_with(" | ".join(values))

    job_entries.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    for row, (_, _, entry) in zip(job_rows, job_entries):
        row.replace_with(entry)

    lines = list(page.stripped_strings)
    links = dict.fromkeys(PRODUCT_PATH.findall(html))
    if links:
        lines.extend(["", "Completed light-curve links"])
        lines.extend(HOST + path for path in links)
    else:
        lines.extend(["", "No completed light-curve links in this response."])
    finished_entries.sort(key=lambda entry: entry[0], reverse=True)
    finished_lines = [f"Finished jobs returned: {len(finished_entries)}"]
    if finished_entries:
        finished_lines.append(job_header)
        finished_lines.extend(entry for _, entry in finished_entries)
    else:
        finished_lines.append("No finished job rows in this response.")
    return "\n".join(lines), "\n".join(finished_lines)


def format_report(html: str) -> str:
    """Return the full status report."""
    return format_reports(html)[0]


def redact_credentials(report: str, values: list[str]) -> str:
    for value in values:
        for variant in (value, quote(value, safe=""), quote_plus(value)):
            report = report.replace(variant, "[redacted]")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pending", action="store_true", help="Show only pending jobs")
    args = parser.parse_args()

    credentials = dotenv_values(ENV_FILE, interpolate=False)
    required = ("ZTF_EMAIL", "ZTF_USERPASS", "ZTF_SHARED_PASSWORD")
    missing = [key for key in required if not credentials.get(key)]
    if missing:
        parser.error(f"Fill in {', '.join(missing)} in {ENV_FILE}.")

    option = "Pending jobs" if args.pending else "All recent jobs"
    log_prefix = "pending" if args.pending else "check"
    started = datetime.now(timezone.utc)
    LOG_DIR.mkdir(exist_ok=True, mode=0o700)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=LOG_DIR,
        prefix=started.strftime(f"{log_prefix}_%Y%m%dT%H%M%SZ_"), suffix=".log", delete=False,
    ) as log:
        log.write(f"Query started (UTC): {started.isoformat()}\nMode: {option}\n")
        log.flush()
        print(f"Status log: {log.name}", flush=True)
        try:
            response = requests.get(
                STATUS_URL,
                auth=("ztffps", credentials["ZTF_SHARED_PASSWORD"]),
                params={
                    "email": credentials["ZTF_EMAIL"],
                    "userpass": credentials["ZTF_USERPASS"],
                    "option": option,
                    "action": "Query Database",
                },
                timeout=300,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            message = f"ZFPS status query failed ({type(error).__name__})."
            log.write(message + "\n")
            parser.exit(1, message + "\n")
        log.write(f"HTTP status: {response.status_code}\n")
        if response.status_code != 200:
            parser.exit(1, f"ZFPS status query returned HTTP {response.status_code}.\n")

        report, finished_report = format_reports(response.text)
        secrets = [credentials[key] for key in required]
        report = redact_credentials(report, secrets)
        log.write(report + "\n")
    if not args.pending:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=LOG_DIR,
            prefix=started.strftime("finished_%Y%m%dT%H%M%SZ_"), suffix=".log", delete=False,
        ) as finished_log:
            finished_log.write(
                f"Query started (UTC): {started.isoformat()}\n"
                f"Source status log: {Path(log.name).name}\n"
                + redact_credentials(finished_report, secrets) + "\n"
            )
        print(f"Finished jobs log: {finished_log.name}")
    print(option)
    print(report)


if __name__ == "__main__":
    main()
