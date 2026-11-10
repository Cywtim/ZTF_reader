# ZTF forced-photometry tools

Submit targets to IPAC's ZTF Forced Photometry Service (ZFPS), track the queue, download completed light curves, and export the measurements as CSV. Run the commands from this directory.

| Command | What it does |
| --- | --- |
| [`submit_ztf`](src/submit_ztf.py) | Submit one target or a batch using JD or MJD bounds. |
| [`checking_ztf`](src/checking_ztf.py) | Query pending or recent jobs and save UTC status reports. |
| [`download_file`](src/download_file.py) | Compare pending snapshots and download products confirmed by the finished log. |
| [`read_ztf`](src/read_ztf.py) | Convert `download/*.txt` to `csv/*.csv` or read a single file from Python. |

## Terminal quick start

Run the following steps in a Bash terminal. If you already downloaded ZTF text files, complete the setup and jump to [step 5](#5-export-csvs-or-read-a-light-curve-in-python).

### 1. Open the project and install the commands

Use Python 3.11 or later and activate the Python environment you want to use. Adjust the `cd` path if your checkout is elsewhere. The editable install adds the dependencies and makes the four commands available in that environment.

```bash
cd ~/Documents/ZTF_reader
python3 -m pip install -e .
submit_ztf --help
```

To install the Python dependencies separately, run `python3 -m pip install -r requirements.txt`. The editable install reads from the same [dependency list](requirements.txt).

For submission, status checks, and downloads, set up your ZFPS credentials. If you need an account, email `ztf@ipac.caltech.edu` to register. Run this once to copy the template if `.env` is missing. [Credential template](.env.example)

```bash
(umask 077; cp -n .env.example .env)
```

Open `.env` in your editor and fill in all three values before making an IPAC request.

The shared password is for the `ztffps` service login. The personal password identifies your ZFPS account. Keep `.env` local. For registration and browser sign-in, see the [feature guidelines](ZTF_FEATURE_GUIDELINES.md).

### 2. Submit targets

Validate a single target and date range with a dry run.

```bash
submit_ztf \
  --position '10h25m30.29s +14d02m07.3s' \
  --mjd-start 58194 --mjd-end 61000 \
  --dry-run
```

**Single-line terminal version**

```bash
submit_ztf --position '10h25m30.29s +14d02m07.3s' --mjd-start 58194 --mjd-end 61000 --dry-run
```

Set the target and dates for your study, then remove `--dry-run` to submit. A quoted position can use HMS/DMS, colon-separated sexagesimal values, or decimal degrees. Use `--jd-start` and `--jd-end` if your dates are already in JD.

For a batch, create a headerless `targets.txt` with one space-separated RA and Dec pair per line.

```text
10h25m30.29s +14d02m07.3s
10:30:00.00 -00:30:00.0
156.42 14.12
```

```bash
submit_ztf --coordinates targets.txt \
  --mjd-start 58194 --mjd-end 61000 --dry-run
```

**Single-line terminal version**

```bash
submit_ztf --coordinates targets.txt --mjd-start 58194 --mjd-end 61000 --dry-run
```

Each batch accepts up to 1,500 positions and shares one date range. The script converts MJD to JD before submitting. A live submission writes `job/submission_*.jsonl` with the positions, JD bounds, and HTTP result. Confirm that the request appears in the queue before treating it as accepted.

### 3. Capture a pending snapshot

```bash
checking_ztf --pending
```

**Terminal version using Python directly**

Run either command from the repository root with the Python dependencies installed.

```bash
python3 -m src.checking_ztf --pending  # Pending jobs
python3 -m src.checking_ztf            # Recent jobs, including finished jobs
```

Save a snapshot while the requests you want to track are still pending or running. The first valid pending snapshot establishes the baseline. IPAC refreshes the status database hourly. If a new submission is missing, check again after the next refresh and search by request ID or coordinates. [ZFPS feature guidelines](ZTF_FEATURE_GUIDELINES.md#check-status-and-download-results)

### 4. Download finished light curves

After a later queue refresh, save another pending snapshot and query recent jobs for the product links.

```bash
checking_ztf --pending
checking_ztf
download_file --dry-run
```

A request qualifies for download if it appeared in an earlier pending snapshot, is absent from the latest valid one, and has a matching product link in a finished log. Keep earlier pending logs so requests remain eligible if their links appear later.

When the preview shows the expected files, download them.

```bash
download_file
ls -1 download/
```

**Terminal version using Python directly**

From the repository root, preview the eligible files first. Run the second command when you are ready to download them.

```bash
python3 -m src.download_file --dry-run
python3 -m src.download_file
```

Reruns skip files already saved in `download/`. If a job finished before you captured it in a pending snapshot, use its link in the finished log or completion email.

**Download only requests that left the queue since the previous check**

With both pending logs already saved, refresh the recent-jobs report and preview the difference.

```bash
python3 -m src.checking_ztf
python3 -m src.download_file --previous-only --dry-run
```

`--previous-only` compares the two newest valid pending logs by request ID. It selects IDs from the previous log that are absent from the current log and have a matching product link in a finished log. If a link is still missing, refresh recent jobs again while keeping the same pending snapshots.

When the preview lists the expected files, save them to `download/`.

```bash
python3 -m src.download_file --previous-only
```

If you have only one pending log, it serves as the baseline. Run `python3 -m src.checking_ztf --pending` after a later queue refresh to get the second snapshot.

### 5. Export CSVs or read a light curve in Python

Run this command to convert the ZTF text files in `download/` to same-named CSV files in `csv/`.

```bash
read_ztf
ls -1 csv/
```

For example, `download/batchfp_req0005176471_lc.txt` becomes `csv/batchfp_req0005176471_lc.csv`. The CSV contains the measurement columns and all epochs, with blank cells for missing values. Rerunning the command skips existing CSVs.

To read a result directly in Python, replace the example filename with one from `download/`.

```python
from src.read_ztf import read_ztf_header, read_ztf_lightcurve

path = "download/batchfp_req0005176471_lc.txt"
header = read_ztf_header(path)
df = read_ztf_lightcurve(path)

print(header)
print(df[["jd", "filter", "forcediffimflux", "forcediffimfluxunc"]].head())
```

Use the original text file to read its request metadata with `read_ztf_header()`. The DataFrame reader keeps every epoch and maps ZTF's `-99999` missing-value marker to `NaN`. For quality cuts, grouping by reference image, and calibration, see the [photometry guidelines](ZTF_FEATURE_GUIDELINES.md#filter-group-and-validate-the-photometry).

## Project layout

The workflow scripts live in [`src/`](src/). [`pyproject.toml`](pyproject.toml) defines the commands, and [`config.py`](config.py) defines the source directory, shared paths, and IPAC service URLs. The editable install uses `.env` and the data folders at the repository root. You can also run `python3 -m src.<module>` from the repository root.

## Where the files go

| Path | Contents |
| --- | --- |
| `job/submission_*.jsonl` | Submitted coordinates, JD bounds, and the HTTP result or network error. |
| `log/pending_*.log` | Queue snapshots created with `checking_ztf --pending`. |
| `log/check_*.log` | Full recent-jobs reports, ordered by processing state and then newest submission. |
| `log/finished_*.log` | Finished jobs, newest completion first, with exit codes and available product links. |
| `download/*_lc.txt` | Original IPAC light-curve files, including request metadata. |
| `csv/*_lc.csv` | Measurement tables exported by `read_ztf.py`. |

Status reports use UTC. A finished row can still have a warning or error, so check its `exitcode`. The local `.env` and generated files in `job/`, `log/`, `download/`, and `csv/` are Git-ignored.
