# ZTF forced-photometry tools

Submit targets to IPAC's ZTF Forced Photometry Service (ZFPS), track the queue, download completed light curves, and export the measurements as CSV. Run the commands from this directory.

| Script | What it does |
| --- | --- |
| [`submit_ztf.py`](submit_ztf.py) | Submit one target or a batch using JD or MJD bounds. |
| [`checking_ztf.py`](checking_ztf.py) | Query pending or recent jobs and save UTC status reports. |
| [`download_file.py`](download_file.py) | Compare pending snapshots and download products confirmed by the finished log. |
| [`read_ztf.py`](read_ztf.py) | Convert `download/*.txt` to `csv/*.csv` or read a single file from Python. |

If you already have ZTF text files in `download/`, go straight to the [CSV export step](#5-export-csvs-or-read-a-light-curve-in-python).

## 1. Set up Python and ZFPS credentials

Use Python 3.11 or later. Install the dependencies in your Python environment.

```bash
python3 -m pip install astropy beautifulsoup4 pandas python-dotenv requests
```

If you need a ZFPS account, email `ztf@ipac.caltech.edu` to register. If you do not already have a local `.env`, copy the template to `.env` beside the scripts. Fill in all three values in your local copy. [Credential template](.env.example)

The shared password is for the `ztffps` service login. The personal password identifies your ZFPS account. Keep `.env` local. For registration and browser sign-in, see the [feature guidelines](ZTF_FEATURE_GUIDELINES.md).

## 2. Submit targets

Validate a single target and date range with a dry run.

```bash
python3 submit_ztf.py \
  --position '10h25m30.29s +14d02m07.3s' \
  --mjd-start 58194 --mjd-end 61000 \
  --dry-run
```

Set the target and dates for your study, then remove `--dry-run` to submit. A quoted position can use HMS/DMS, colon-separated sexagesimal values, or decimal degrees. Use `--jd-start` and `--jd-end` if your dates are already in JD.

For a batch, create a headerless `targets.txt` with one space-separated RA and Dec pair per line.

```text
10h25m30.29s +14d02m07.3s
10:30:00.00 -00:30:00.0
156.42 14.12
```

```bash
python3 submit_ztf.py --coordinates targets.txt \
  --mjd-start 58194 --mjd-end 61000 --dry-run
```

Each batch accepts up to 1,500 positions and shares one date range. The script converts MJD to JD before submitting. A live submission writes `job/submission_*.jsonl` with the positions, JD bounds, and HTTP result. Confirm that the request appears in the queue before treating it as accepted.

## 3. Capture a pending snapshot

```bash
python3 checking_ztf.py --pending
```

Save a snapshot while the requests you want to track are still pending or running. The first valid pending snapshot establishes the baseline. IPAC refreshes the status database hourly. If a new submission is missing, check again after the next refresh and search by request ID or coordinates. [ZFPS feature guidelines](ZTF_FEATURE_GUIDELINES.md#check-status-and-download-results)

## 4. Download finished light curves

After a later queue refresh, save another pending snapshot and query recent jobs for the product links.

```bash
python3 checking_ztf.py --pending
python3 checking_ztf.py
python3 download_file.py --dry-run
```

A request qualifies for download if it appeared in an earlier pending snapshot, is absent from the latest valid one, and has a matching product link in a finished log. Keep earlier pending logs so requests remain eligible if their links appear later.

When the preview shows the expected files, run `python3 download_file.py` to save them in `download/`. Reruns skip files already saved there. If a job finished before you captured it in a pending snapshot, use its link in the finished log or completion email.

## 5. Export CSVs or read a light curve in Python

Run this command to convert the ZTF text files in `download/` to same-named CSV files in `csv/`.

```bash
python3 read_ztf.py
```

For example, `download/batchfp_req0005176471_lc.txt` becomes `csv/batchfp_req0005176471_lc.csv`. The CSV contains the measurement columns and all epochs, with blank cells for missing values. Rerunning the command skips existing CSVs.

To read a result directly in Python, replace the example filename with one from `download/`.

```python
from read_ztf import read_ztf_header, read_ztf_lightcurve

path = "download/batchfp_req0005176471_lc.txt"
header = read_ztf_header(path)
df = read_ztf_lightcurve(path)

print(header)
print(df[["jd", "filter", "forcediffimflux", "forcediffimfluxunc"]].head())
```

Use the original text file to read its request metadata with `read_ztf_header()`. The DataFrame reader keeps every epoch and maps ZTF's `-99999` missing-value marker to `NaN`. For quality cuts, grouping by reference image, and calibration, see the [photometry guidelines](ZTF_FEATURE_GUIDELINES.md#filter-group-and-validate-the-photometry).

## Where the files go

| Path | Contents |
| --- | --- |
| `job/submission_*.jsonl` | Submitted coordinates, JD bounds, and the HTTP result or network error. |
| `log/pending_*.log` | Queue snapshots created with `checking_ztf.py --pending`. |
| `log/check_*.log` | Full recent-jobs reports, ordered by processing state and then newest submission. |
| `log/finished_*.log` | Finished jobs, newest completion first, with exit codes and available product links. |
| `download/*_lc.txt` | Original IPAC light-curve files, including request metadata. |
| `csv/*_lc.csv` | Measurement tables exported by `read_ztf.py`. |

Status reports use UTC. A finished row can still have a warning or error, so check its `exitcode`. The local `.env` and generated files in `job/`, `log/`, `download/`, and `csv/` are Git-ignored.
