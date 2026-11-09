"""Submit targets to the IPAC ZTF Forced Photometry Service."""

import argparse
from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path
from tempfile import NamedTemporaryFile
import warnings

from astropy import units as u
from astropy.coordinates import Angle
from astropy.utils.exceptions import AstropyWarning
import requests
from dotenv import dotenv_values


from config import CREDENTIAL_KEYS, ENV_FILE, JOB_DIR, SUBMIT_URL, ZTF_AUTH_USER


MAX_POSITIONS = 1500
MJD_OFFSET = 2400000.5


def parse_position(values: list[str]) -> tuple[float, float]:
    """Convert a decimal-degree or sexagesimal RA/Dec pair to degrees."""
    if len(values) != 2:
        raise ValueError("Expected one RA and one Dec.")
    ra, dec = values
    with warnings.catch_warnings():
        warnings.simplefilter("error", AstropyWarning)
        try:
            ra_deg = Angle(ra, unit=u.hourangle).degree if "h" in ra or ":" in ra else float(ra)
            dec_deg = Angle(dec, unit=u.deg).degree if "d" in dec or ":" in dec else float(dec)
        except (ValueError, AstropyWarning) as error:
            raise ValueError("Use decimal degrees or an HMS RA and DMS Dec.") from error
    if not (0 <= ra_deg < 360 and -90 <= dec_deg <= 90):
        raise ValueError("Expected 0 <= RA < 360 and -90 <= Dec <= 90 in degrees.")
    return float(ra_deg), float(dec_deg)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument(
        "--position", nargs="+", metavar="COORD",
        help="One RA Dec pair in decimal degrees or HMS/DMS. Quote the pair for negative DMS.",
    )
    targets.add_argument(
        "--coordinates", type=Path, help="Headerless text file with one RA Dec pair per line"
    )
    start = parser.add_mutually_exclusive_group(required=True)
    start.add_argument("--jd-start", type=float)
    start.add_argument("--mjd-start", type=float)
    end = parser.add_mutually_exclusive_group(required=True)
    end.add_argument("--jd-end", type=float)
    end.add_argument("--mjd-end", type=float)
    parser.add_argument("--dry-run", action="store_true", help="Validate the input locally")
    args = parser.parse_args()

    if (args.jd_start is None) != (args.jd_end is None):
        parser.error("Use both JD flags or both MJD flags.")
    if args.jd_start is None:
        jd_start, jd_end = args.mjd_start + MJD_OFFSET, args.mjd_end + MJD_OFFSET
    else:
        jd_start, jd_end = args.jd_start, args.jd_end
    if not (isfinite(jd_start) and isfinite(jd_end) and jd_start < jd_end):
        parser.error("Provide finite dates with the start earlier than the end.")

    if args.position:
        try:
            positions = [parse_position(" ".join(args.position).split())]
        except ValueError as error:
            parser.error(str(error))
    else:
        try:
            with args.coordinates.open(encoding="utf-8") as source:
                positions = []
                for number, line in enumerate(source, start=1):
                    if line.strip():
                        try:
                            positions.append(parse_position(line.split()))
                        except ValueError as error:
                            parser.error(f"{args.coordinates}:{number}: {error}")
        except OSError as error:
            parser.error(str(error))

    if not 1 <= len(positions) <= MAX_POSITIONS:
        parser.error(f"Provide between 1 and {MAX_POSITIONS} positions per batch.")
    payload = {
        "ra": json.dumps([ra for ra, _ in positions]),
        "dec": json.dumps([dec for _, dec in positions]),
        "jdstart": json.dumps(jd_start),
        "jdend": json.dumps(jd_end),
    }
    print(f"{len(positions)} position(s), JD {jd_start} to {jd_end}")
    if args.dry_run:
        return

    credentials = dotenv_values(ENV_FILE, interpolate=False)
    missing_keys = [key for key in CREDENTIAL_KEYS if not credentials.get(key)]
    if missing_keys:
        parser.error(f"Fill in {', '.join(missing_keys)} in {ENV_FILE}.")

    payload["email"] = credentials["ZTF_EMAIL"]
    payload["userpass"] = credentials["ZTF_USERPASS"]

    started = datetime.now(timezone.utc)
    JOB_DIR.mkdir(exist_ok=True, mode=0o700)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=JOB_DIR,
        prefix=started.strftime("submission_%Y%m%dT%H%M%SZ_"), suffix=".jsonl", delete=False,
    ) as record:
        submission = {
            "event": "submission_attempt",
            "timestamp_utc": started.isoformat(),
            "positions_deg": [{"ra": ra, "dec": dec} for ra, dec in positions],
            "jd_start": jd_start,
            "jd_end": jd_end,
        }
        record.write(json.dumps(submission) + "\n")
        record.flush()
        print(f"Submission record: {record.name}", flush=True)
        try:
            response = requests.post(
                SUBMIT_URL,
                auth=(ZTF_AUTH_USER, credentials["ZTF_SHARED_PASSWORD"]),
                data=payload,
                timeout=60,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            record.write(json.dumps({
                "event": "submission_status_unknown",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": type(error).__name__,
            }) + "\n")
            parser.exit(1, f"Submission status unknown ({type(error).__name__}). Check ZFPS before retrying.\n")
        record.write(json.dumps({
            "event": "http_response",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "http_status": response.status_code,
        }) + "\n")
    if not 200 <= response.status_code < 300:
        parser.exit(1, f"ZFPS returned HTTP {response.status_code}. Check ZFPS before retrying.\n")

    print(f"ZFPS returned HTTP {response.status_code}. Check your email and ZFPS job status.")


if __name__ == "__main__":
    main()
