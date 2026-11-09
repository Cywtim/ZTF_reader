# ZTF forced-photometry feature guidelines

_A reference for submitting requests, reading IPAC results, and developing light-curve analysis features in this workspace._

## How the two guides fit together

| Guide | What it covers | Where to look |
| --- | --- | --- |
| [Generating Lightcurves from Forced PSF-fit Photometry on ZTF Difference Images](ztf_forced_photometry.pdf), v2.3 | The original single-position service, its output columns and warnings, and recipes for differential and total photometry | §§2–6 for requests and delivery, §§7–9 for interpreting output, §§10–14 for analysis |
| [A New Forced Photometry Service for the Zwicky Transient Facility](ztf_zfps_userguide.pdf), 2023 | The batch interface, PSF-fit methodology, and updated guidance on quality cuts, baseline checks, calibration, and stacking | §3 and Appendices A–B for service calls, §§4–5 for methodology and status, §6 for analysis |

Use the 2023 guide for batch submission and retrieval. Use the v2.3 guide when working with older files or the original single-position interface. Both describe flux measured at a specified position on existing ZTF difference images. Returned epochs depend on archived difference-image coverage and the account's data access. A catalog object ID is optional because the request is position-based.

## Register and sign in

1. Email `ztf@ipac.caltech.edu` to request access to the **ZTF Forced Photometry Service (ZFPS)**. Include your affiliation and mention any membership in the ZTF Partnership or Caltech ZTF Project. Use your institutional address if available. IPAC issues a personal password and sends completion notices to the address you registered. Accounts from the original service were enrolled in the batch service with the same privileges, according to the 2023 guide.
2. When your browser displays the HTTP authentication dialog for a ZFPS page or download, enter the shared username `ztffps` and the shared service password. Both PDFs publish `dontgocrazy!` as the shared password at the time of writing. Check the [ZFPS service page](https://ztfweb.ipac.caltech.edu/batchfp.html) for credential or maintenance updates.
3. When the **web form** asks for account details, enter your registered email and the personal password IPAC issued to you. Appendix A calls this password `userpass`. For the workspace script, set the following values in the local `.env` beside `submit_ztf.py`.

   | Key | Value |
   | --- | --- |
   | `ZTF_EMAIL` | Your registered email |
   | `ZTF_USERPASS` | Your personal ZFPS password |
   | `ZTF_SHARED_PASSWORD` | The shared password for `ztffps` |

The shared credentials open the service. The personal credentials associate requests and status queries with your account. Keep personal credentials out of example commands, logs, and version control. See v2.3 §§2–3 and the 2023 guide §§3–3.1 and Appendix A.

## Submit a request

### Choose the position and dates

- Use ICRS or J2000 coordinates consistent with ZTF astrometry. The workspace script accepts decimal degrees or HMS RA and DMS Dec and sends decimal degrees to IPAC. Spot-check positions against calibrated images in the [IRSA ZTF archive](https://irsa.ipac.caltech.edu/Missions/ztf.html). Retain a target ID to coordinate mapping for later identification.
- Supply both dates in either JD or MJD, with start earlier than end. The script adds `2400000.5` to MJD bounds for the ZFPS request. The documented survey start is JD `2458194.5` (MJD `58194.0`, 2018-03-17 00:00 UTC). The original single-position form defaults to the survey start and current JD when dates are omitted.
- For a transient, include enough time outside the event to obtain roughly 30 quiet epochs if possible. Calendar coverage depends on cadence. The service searches existing archived difference images in (g), (r), and (i). The first available difference image may be later than the first science exposure, and proprietary epochs depend on account access.

### Batch submission from the workspace

Install the submission dependencies if needed with `python3 -m pip install requests python-dotenv astropy`. Run this from the workspace with your desired position and dates.

```bash
python3 submit_ztf.py \
  --position '10h25m30.29s +14d02m07.3s' \
  --mjd-start 58194 --mjd-end 61000 \
  --dry-run
```

Remove `--dry-run` to submit. For multiple targets, use `--coordinates List_of_RA_Dec.txt` in place of `--position`. Put one space-separated RA and Dec pair per line, with no header. A line can use `10h25m30.29s +14d02m07.3s`, `10:25:30.29 +14:02:07.3`, or `156.3762083 14.0353611`. Quote the full pair when passing a negative DMS declination to `--position`. All targets share the date bounds supplied on the command line. Use `--jd-start` and `--jd-end` to supply JD directly.

Each submission attempt writes a timestamped JSON Lines record under `job/`. The first line records the coordinates and JD bounds before the network call. The second records the HTTP status or the error type if the outcome is unknown. These local records contain no account credentials. A dry run creates no submission record.

Appendix A sends an HTTP POST to `https://ztfweb.ipac.caltech.edu/cgi-bin/batchfp.py/submit`. It uses shared HTTP Basic authentication and form fields `ra` and `dec` as JSON arrays, `jdstart` and `jdend` as JSON numbers, and `email` and `userpass` as account credentials. The guide documents 1,500 positions per submission, 15,000 outstanding distinct positions per user, and a 90-day interval before requesting the same positions again. HTTP 413 can indicate an oversized batch. After a timeout or ambiguous response, check the job list before retrying. A successful HTTP response is the response to the submission step. Processing happens afterward.

### Original single-position web form

Open the [single-position request form](https://ztfweb.ipac.caltech.edu/cgi-bin/requestForcedPhotometry.cgi), enter the shared credentials at the browser prompt, then enter RA, Dec, optional JD bounds, and your personal credentials on the form. The older guide also documents a command-line request with query parameters `ra`, `dec`, `jdstart`, `jdend`, `email`, and `userpass`. Use the batch script for the workspace CLI workflow. The v2.3 guide's 100-position queue limit refers to the original service.

## Check status and download results

### Check a batch job in your browser

1. Open the [batch request status form](https://ztfweb.ipac.caltech.edu/cgi-bin/getBatchForcedPhotometryRequests.cgi). Use shared credentials if the browser asks for HTTP authentication.
2. Enter your registered email and personal `userpass` in the form. Choose **Pending jobs** to check the queue or **All recent jobs** to look for finished requests and download links. Select **Query Database**.
3. Check again after the next hourly refresh if a recent request or result is missing. The batch guide says the status database is refreshed at the top of each hour and covers roughly the last 30 days. A batch completion email is sent after all positions in that submission finish. Query time can be several minutes.

For an original single-position job, use the [single-position status form](https://ztfweb.ipac.caltech.edu/cgi-bin/getForcedPhotometryRequests.cgi). The v2.3 guide also describes hourly refreshes and about one month of request history.

### Check a batch job from Python

Run [`checking_ztf.py`](checking_ztf.py) from the workspace. It reads the same `.env` as the submitter and prints the status response and any completed light-curve links. If needed, install its dependencies with `python3 -m pip install requests python-dotenv beautifulsoup4`.

```bash
python3 checking_ztf.py            # All recent jobs
python3 checking_ztf.py --pending  # Pending jobs only
```

The script follows Appendix B. It sends an HTTP GET to the batch status URL with `email`, `userpass`, `option` (`All recent jobs` or `Pending jobs`), and `action` (`Query Database`).

Each status query writes a timestamped report under `log/`, including the query mode, HTTP status or network error, and any returned job details and download links. The terminal and log show pending jobs first, followed by running and finished jobs, with newest requests first in each group. They show `created`, `started`, and `ended` in UTC, interpreting IPAC timestamps without a timezone as US Pacific time. Both `job/` and `log/` are Git-ignored.

The default recent-jobs check writes `log/check_*.log` and a separate `log/finished_*.log`. The finished log contains only jobs with an end time, ordered by most recent completion. Check each row's exit code to distinguish successful processing from a job that finished with a warning or error. The `--pending` check writes `log/pending_*.log`.

An HTTP 200 can return a page with no completed products. Use the browser's status page to distinguish pending work, expired history, or a form error. The GET request includes the personal password as a query parameter, so avoid logging the request URL.

### Save the light-curve files

Use [`download_file.py`](download_file.py) to download finished products that were previously pending. Save an initial pending snapshot with `python3 checking_ztf.py --pending`. The first snapshot serves as a baseline. After a later status refresh, run the following commands.

```bash
python3 checking_ztf.py --pending
python3 checking_ztf.py
python3 download_file.py --dry-run
```

Remove `--dry-run` to save eligible products to `download/`. The downloader checks IDs seen in earlier valid pending snapshots against the latest valid snapshot. It requires a matching product link in a finished log, so a request can still be picked up if its link appears in a later check. Existing files are skipped.

To download a product manually, follow these steps.

1. Use the exact product link from the completion email or batch status response. It contains a checksum, so the request ID alone cannot reconstruct it. Open the link in your browser and use the shared `ztffps` credentials if prompted.
2. To download from a terminal, replace both placeholders below with the filename and exact URL. With just the username, curl prompts for the shared password.

   ```bash
   curl --fail --user ztffps \
     --output 'batchfp_reqXXXXXXXXXX_lc.txt' \
     'PASTE_EXACT_ZTF_PRODUCT_URL'
   ```

3. Save the completion email or product links, request IDs, and downloaded files. A filename such as `batchfp_req0005176276_lc.txt` contains the per-position request ID. Use the requested RA and Dec in the header to match the result to your target list. Open the text file to verify it contains ZTF metadata and measurement rows before passing it to the reader.

Service instructions are documented in v2.3 §§2–6 and the 2023 guide §3 and Appendices A–B. The live forms require service access.

## Read and preserve the result

- Keep the original `*_lc.txt` file. Its `#` lines contain request metadata and column definitions. The column-name line can contain commas, while the measurement rows are whitespace-delimited. Read names from the file instead of assuming a fixed column count across releases.
- Expose header access separately from table access. Keep requested coordinates, requested JD range, and access information available for provenance. Preserve the per-epoch quality and reference-image fields.
- Keep every parsed epoch in the raw DataFrame and represent the `-99999` sentinel as missing. Valid negative difference fluxes are measurements. Apply quality filtering as a separate step.
- Use `jd` as the exposure start time. Keep `field`, `ccdid`, `qid`, `filter`, and `rfid` where present to identify distinct reference images. Use `zpdiff`, `forcediffimflux`, and `forcediffimfluxunc` for PSF difference photometry. Aperture measurements can serve as a cross-check.

Source sections for parsing and interpretation are v2.3 §§7–9 and the 2023 guide §§4–6.

### Diagnose processing codes

The batch guide's Table 1 and the older guide's §9 define `procstatus` at the measurement level. These are distinct from HTTP responses and queue status.

| Code | Meaning and interpretation |
| --- | --- |
| `0` | Processing succeeded. Apply science-image quality cuts separately. |
| `52` | Batch processing reached an input-file limit. The guide recommends a later JD window for the remaining coverage. This code is separate from the 1,500-position submission limit. |
| `54`, `55` | Too few background pixels or too many bad pixels, respectively. A valid PSF measurement may be unavailable. |
| `56` | Bad or blank pixels may have affected the measurement. Compare results with these rows excluded. |
| `57`, `58` | No nearby reference catalog source or missing reference PSF catalog, respectively. These flags are particularly relevant when deriving total flux. |
| `59`, `60` | The older guide documents suspect uncertainties for some early difference images and an invalid upsampled PSF size, respectively. |
| `61` | Position outside the image or too close to the edge. |
| `62`, `65` | Requested start or end, respectively, precedes the survey start. Check the request dates. |
| `63` | No matching epochs returned. Check coverage, date range, and data access. |
| `64`, `255` | Processing failure or database/other error, respectively. Consult any accompanying log. |

The local batch file also has `diffimgstatus`, with `1` meaning good and `0` meaning bad according to its header. Read the file's definitions because fields and flags can vary with the producer version.

## Filter, group, and validate the photometry

| Check | Guideline |
| --- | --- |
| Required measurements | Use finite times, zero points, and fluxes with finite, positive flux uncertainties. |
| Science-image quality | The batch guide advises dropping epochs with `infobitssci >= 33554432`, `scisigpix > 25` DN, or seeing worse than 4 arcsec. The local example labels `sciinpseeing` in pixels. Check the units before applying a numeric seeing threshold. |
| Processing flags | Consult the relevant guide's code table. Code `0` indicates success, `55` indicates too many bad pixels in the batch guide, and `56` warns that bad or blank pixels may affect photometry. Keep the flags available when comparing quality selections. |
| Reference groups | Start with separate series by `field`, `ccdid`, `qid`, and `filter`. Split further if `rfid` changes. Inspect each group's baseline and calibration before combining series from different reference images. |
| Transient baseline | Plot signed difference flux against JD. If a stationary interval outside the event shows an offset, subtract a median or trimmed mean from that group's fluxes. The batch guide suggests at least 30 quiet epochs. Inspect `refjdstart` and `refjdend` for possible transient contamination. |
| Uncertainty validation | Check whether the typical reduced PSF-fit chi-square in `forcediffimchisq` is near one. Inspect the robust scatter of baseline-corrected flux divided by its uncertainty in a quiet interval. Record any uncertainty rescaling and the interval used. |

Keep the signed flux and uncertainty available even when the display uses magnitude limits. Save the applied cuts and counts by filter so the selection can be reproduced. See v2.3 §§8–11 and the 2023 guide §§5–6.3.

## Calibrate and combine measurements

### Differential photometry for transients

Use baseline-corrected flux `F` and validated uncertainty `s`. The guides' example classifies `F/s > 3` as a detection and uses a 5-sigma upper limit for other epochs. Store a detection flag and keep the limit separate from measured magnitudes.

| Output | Formula |
| --- | --- |
| Differential magnitude for a detection | `zpdiff - 2.5 * log10(F)` |
| Magnitude uncertainty for a detection | `1.0857 * s / F` |
| Magnitude corresponding to a 5-sigma flux limit | `zpdiff - 2.5 * log10(5 * s)` |

See v2.3 §12 and the 2023 guide §6.4.

The basic magnitude formulas assume zero source color in the Pan-STARRS1 system. If you have suitable source colors, the guides describe an additive correction using `clrcoeff × (g_PS1 − r_PS1)` for ZTF (g) and (r), or `clrcoeff × (r_PS1 − i_PS1)` for ZTF (i). See v2.3 §13 and the 2023 guide §6.5.

### Total photometry for variable sources

Verify that the reference catalog source matches the target and that its PSF photometry is appropriate. Both guides suggest a reference-match separation near or below 1 arcsec and checking the source shape. For an extended host or ambiguous match, treat the difference light curve as the directly measured product and establish a suitable reference flux before deriving total flux.

Put reference flux on the epoch's scale using `F_ref = 10**(0.4 * (zpdiff - nearestrefmag))`, then add it to the difference flux. Preserve the reference baseline when reconstructing total variability. Follow the guide's uncertainty treatment for the covariance introduced by using the same reference image. The batch guide uses variance subtraction under its same-reference assumption and advises variance addition if that assumption fails or the result is nonpositive. See v2.3 §13 and the 2023 guide §6.5.

### Combining epochs

Within a filter, use a time bin in which the signal can reasonably be treated as constant. After quality checks and any needed baseline correction, rescale each flux and uncertainty by `10**(0.4 * (ZP_common - zpdiff))`. Use an inverse-variance weighted mean and an uncertainty of `1 / sqrt(sum(weights))` for independent errors. Shared reference images and subtraction systematics can limit the improvement. See v2.3 §14 and the 2023 guide §6.6.

## Workspace implementation

| Feature | Current entry point or implementation guideline |
| --- | --- |
| Submit a position or coordinate list | [`submit_ztf.py`](submit_ztf.py) accepts decimal degrees or HMS/DMS, JD or MJD bounds, and a credential-free `--dry-run`. |
| Read output and provenance | [`read_ztf.py`](read_ztf.py) exposes `read_ztf_lightcurve(path)` for a DataFrame and `read_ztf_header(path)` for header text. |
| Verify reader compatibility | The [local example](Liu_IMBH/batchfp_req0005176276_lc.txt) has 1,417 rows and 41 columns, including signed PSF difference fluxes. The current reader expects a one-line column header starting with `sindex`. Supporting older `index` or wrapped headers requires additional reader compatibility work. |
| Extend the workflow | Keep downloading separate from submission and status checks. Keep filtering, calibration, and plotting separate from parsing. Carry quality flags, reference group, correction history, and upper-limit status into derived products. |
