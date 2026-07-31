"""
NIS fixed-width DAT file parser.

Two steps to use:
  1. parse_sas_columns(sas_text) or parse_r_columns(r_text) → column map,
     depending on which format the year's sidecar file uses (see
     NISYear.format_type in nis_catalog.py — legacy years <=2014 ship a SAS
     import program, 2016+ ships an R script instead).
  2. stream_dat(url, columns, select) → iterator of row dicts

All parsing is streaming; the DAT file is never written to disk.
"""

from __future__ import annotations

import re
from typing import Iterator

import requests


def parse_sas_columns(sas_text: str) -> dict[str, tuple[int, int]]:
    """
    Parse a NIS SAS import program and return column positions.

    Returns {VARNAME: (start, end)} where positions are 0-indexed, end exclusive —
    suitable for Python slice notation: line[start:end].

    Handles both NIS pointer notation and column-range notation:
      @1  SEQNUMC  7.        →  SEQNUMC: (0, 7)
      YEAR 8-11              →  YEAR:    (7, 11)
    """
    columns: dict[str, tuple[int, int]] = {}

    # Strip SAS block comments  /* ... */
    sas_text = re.sub(r"/\*.*?\*/", " ", sas_text, flags=re.DOTALL)
    # Strip SAS statement comments  * text ;
    sas_text = re.sub(r"(?m)^\s*\*[^;]*;", " ", sas_text)

    # Isolate the INPUT block (everything between INPUT and the closing ;)
    m = re.search(r"\bINPUT\b(.*?);", sas_text, re.DOTALL | re.IGNORECASE)
    if not m:
        return columns

    block = m.group(1)

    # Pointer notation:  @COL  VARNAME  WIDTH.
    for hit in re.finditer(r"@(\d+)\s+(\w+)\s+(\d+)\.", block, re.IGNORECASE):
        start = int(hit.group(1)) - 1  # SAS is 1-indexed
        name = hit.group(2).upper()
        width = int(hit.group(3))
        columns[name] = (start, start + width)

    # Column-range notation:  VARNAME  START-END
    # Only used as fallback when the pointer form found nothing.
    if not columns:
        for hit in re.finditer(r"(\w+)\s+(\d+)-(\d+)", block, re.IGNORECASE):
            name = hit.group(1).upper()
            start = int(hit.group(2)) - 1
            end = int(hit.group(3))
            columns[name] = (start, end)

    return columns


def parse_r_columns(r_text: str) -> dict[str, tuple[int, int]]:
    """
    Parse a NIS R import script (2016+ years) and return column positions.

    CDC's 2015+ file hosting (ftp.cdc.gov/pub/VACCINES_NIS/) ships an R
    import script instead of a SAS program — no .sas sidecar exists there at
    all. The script builds a flat LIST.NAMEWIDTH vector of alternating
    "VARNAME", WIDTH pairs and calls read.fwf(widths=...) on it, e.g.:

      LIST.NAMEWIDTH <-
      c("SEQNUMC",6,
      "SEQNUMHH",5,
      ...
      )

    Unlike SAS pointer notation, these are widths, not absolute offsets —
    but the list is sequential with no skipped bytes, so a running sum of
    widths reconstructs the same (start, end) positions read.fwf() uses.

    Returns {VARNAME: (start, end)}, 0-indexed / end-exclusive — same shape
    as parse_sas_columns().
    """
    columns: dict[str, tuple[int, int]] = {}

    m = re.search(r"LIST\.NAMEWIDTH\s*<-\s*c\((.*?)\)", r_text, re.DOTALL)
    if not m:
        return columns

    pos = 0
    for hit in re.finditer(r'"(\w+)"\s*,\s*(\d+)', m.group(1)):
        name = hit.group(1).upper()
        width = int(hit.group(2))
        columns[name] = (pos, pos + width)
        pos += width

    return columns


def stream_dat(
    dat_url: str,
    columns: dict[str, tuple[int, int]],
    select: set[str] | None = None,
    chunk_size: int = 65536,
    timeout: int = 180,
) -> Iterator[dict[str, str]]:
    """
    Stream a NIS DAT file from URL, yielding one dict per survey respondent.

    dat_url:    Direct URL to the .dat file (not saved to disk).
    columns:    Column map from parse_sas_columns().
    select:     Set of UPPERCASE variable names to include; None returns all.
    chunk_size: HTTP read chunk size in bytes (default 64 KB).
    timeout:    HTTP connect+read timeout in seconds.

    Values are raw strings exactly as they appear in the file.
    See the NIS codebook (PDF) for numeric code meanings.
    """
    active = {k: v for k, v in columns.items() if select is None or k in select}

    resp = requests.get(dat_url, stream=True, timeout=timeout)
    resp.raise_for_status()

    buf = b""
    for chunk in resp.iter_content(chunk_size=chunk_size):
        buf += chunk
        lines = buf.split(b"\n")
        buf = lines[-1]  # keep the incomplete trailing fragment
        for raw in lines[:-1]:
            line = raw.rstrip(b"\r").decode("latin-1")
            if not line:
                continue
            yield _extract(line, active)

    # flush any remaining bytes after the last newline
    if buf:
        line = buf.rstrip(b"\r").decode("latin-1")
        if line:
            yield _extract(line, active)


def _extract(line: str, active: dict[str, tuple[int, int]]) -> dict[str, str]:
    return {name: line[s:e].strip() if e <= len(line) else "" for name, (s, e) in active.items()}
