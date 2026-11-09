"""Read ZTF light curves and convert downloaded text files to CSV."""

import argparse
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from typing import TextIO

import pandas as pd


from config import CSV_DIR, DOWNLOAD_DIR


def _read_header(source: TextIO) -> list[str]:
    lines = []
    for line in source:
        lines.append(line)
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            columns = stripped.replace(",", " ").split()
            if columns[0:1] == ["sindex"] and "forcediffimflux" in columns:
                return lines
            break
    raise ValueError(f"No ZTF forced-photometry column header found in {source.name}")


def read_ztf_header(path: str | Path) -> str:
    """Return the request metadata and column descriptions as text."""
    with Path(path).open(encoding="utf-8") as source:
        return "".join(_read_header(source))


def read_ztf_lightcurve(path: str | Path) -> pd.DataFrame:
    """Return all epochs, with ZTF's -99999 missing values read as NaN."""
    with Path(path).open(encoding="utf-8") as source:
        header = _read_header(source)[-1]
        columns = header.replace(",", " ").split()

        data = pd.read_csv(
            source,
            sep=r"\s+",
            comment="#",
            header=None,
            na_values=[-99999],
        )

    if data.shape[1] != len(columns):
        raise ValueError(f"ZTF column header and data have different widths in {path}")
    data.columns = columns
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert ZTF light-curve text files in download/ to CSV files in csv/."
    )
    parser.parse_args()

    sources = sorted(path for path in DOWNLOAD_DIR.glob("*.txt") if path.is_file())
    if not sources:
        print(f"No text files found in {DOWNLOAD_DIR}.")
        return 0

    CSV_DIR.mkdir(mode=0o700, exist_ok=True)
    failed = False
    for source in sources:
        destination = CSV_DIR / source.with_suffix(".csv").name
        if destination.exists():
            print(f"Skipped existing {destination}")
            continue

        temporary = None
        try:
            data = read_ztf_lightcurve(source)
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=CSV_DIR, delete=False
            ) as output:
                temporary = Path(output.name)
                data.to_csv(output, index=False)
            destination.hardlink_to(temporary)
            print(f"Saved {destination} ({len(data)} rows)")
        except FileExistsError:
            print(f"Skipped existing {destination}")
        except (OSError, ValueError) as error:
            print(f"Could not convert {source.name}: {error}", file=sys.stderr)
            failed = True
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
