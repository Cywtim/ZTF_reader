"""Convert ZTF forced photometry to MJD and difference flux density in microJy."""

import argparse
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

import pandas as pd

# Allow both `python -m src.ztf_flux_reader` and direct script execution.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import DOWNLOAD_DIR, FLUX_DIR
from src.read_ztf import read_ztf_lightcurve


REQUIRED_COLUMNS = ("jd", "forcediffimflux", "forcediffimfluxunc", "zpdiff", "filter")


def read_ztf_flux(path: str | Path) -> pd.DataFrame:
    """Read an original ZTF TXT/CSV as mjd, flux, flux_err, band.

    Flux and its 1-sigma statistical error are in microJy (AB calibration):
    flux = forcediffimflux * 10**(0.4 * (23.9 - zpdiff)).
    This is science-minus-reference flux, not total source flux. Zero-point
    uncertainty is not included. Preserve row order, negative flux, and all
    epochs; map missing values (-99999) to NaN. No quality cuts are applied.
    """
    path = Path(path)
    if path.suffix.lower() == ".txt":
        data = read_ztf_lightcurve(path)
    elif path.suffix.lower() == ".csv":
        data = pd.read_csv(path, na_values=[-99999])
    else:
        raise ValueError("Input must be an original ZTF .txt or .csv file")

    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"Missing ZTF columns: {', '.join(missing)}")
    numeric = data[list(REQUIRED_COLUMNS[:-1])].apply(pd.to_numeric, errors="raise")
    numeric = numeric.replace([-99999, float("inf"), -float("inf")], float("nan"))
    scale = 10.0 ** (0.4 * (23.9 - numeric["zpdiff"]))
    return pd.DataFrame({
        "mjd": numeric["jd"] - 2400000.5,
        "flux": numeric["forcediffimflux"] * scale,
        "flux_err": numeric["forcediffimfluxunc"] * scale,
        "band": data["filter"],
    })


def save_ztf_flux(path: str | Path, output_dir: str | Path = FLUX_DIR) -> Path:
    """Save a flux CSV without overwriting an existing file; return its path.

    Missing cells are blank. Output is <input stem>_diff_flux_uJy.csv.
    Raises FileExistsError if the destination already exists.
    """
    path, output_dir = Path(path), Path(output_dir)
    destination = output_dir / f"{path.stem}_diff_flux_uJy.csv"
    if destination.exists():
        raise FileExistsError(f"Output already exists: {destination}")
    data = read_ztf_flux(path)
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=output_dir, delete=False
        ) as output:
            temporary = Path(output.name)
            data.to_csv(output, index=False, na_rep="")
        destination.hardlink_to(temporary)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert original ZTF TXT/CSV to mjd, flux, flux_err, band in flux/. "
        "Flux and 1-sigma error are difference flux density in microJy; no quality cuts."
    )
    parser.add_argument(
        "inputs", nargs="*", type=Path,
        help="Input TXT/CSV files (default: all download/*.txt).",
    )
    parser.add_argument("--output-dir", type=Path, default=FLUX_DIR,
                        help="Output directory (default: project flux/).")
    args = parser.parse_args()
    sources = args.inputs or sorted(p for p in DOWNLOAD_DIR.glob("*.txt") if p.is_file())
    if not sources:
        print(f"No text files found in {DOWNLOAD_DIR}.")
        return 0
    failed = False
    for source in sources:
        try:
            destination = save_ztf_flux(source, args.output_dir)
            print(f"Saved {destination} (difference flux and 1-sigma error in microJy)")
        except FileExistsError as error:
            print(f"Skipped existing: {error}")
        except (OSError, ValueError) as error:
            print(f"Could not convert {source}: {error}", file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
