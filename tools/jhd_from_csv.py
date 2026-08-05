"""Standalone CSV -> Jagannatha Hora .jhd converter.

This is the source for the shipped ``JhdFromCsv.exe``. It deliberately imports
NOTHING outside the standard library — not even ``pyjhora_batch`` — because a
.jhd file holds only the birth *inputs* (date, time, timezone, place). No
ephemeris, no chart calculation, therefore no swisseph, no PyQt, no data files
to bundle. That keeps the frozen binary a few MB and makes it work on a machine
with no Python installed.

The encoding rules below are duplicated from ``pyjhora_batch/jhd_writer.py``
rather than imported, and the two must be kept in step;
``tools/test_jhd_from_csv.py`` fails if their output ever diverges.

Usage (all three work):
    JhdFromCsv.exe partners.csv          # argument
    <drag partners.csv onto the exe>     # same thing, Explorer supplies argv
    <double-click the exe>               # uses partners.csv sitting beside it

Output goes to a ``jhd`` folder next to the CSV unless ``-o`` says otherwise.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

DEFAULT_CSV_NAME = "partners.csv"
DEFAULT_OUT_DIRNAME = "jhd"
DEFAULT_COUNTRY = "India"
COUNTRY_INDEX = "105"          # JHora's atlas index for India (line 12)

_DATE_RE = re.compile(r"^\s*\d{1,5},\d{1,2},\d{1,2}\s*$")
_TIME_RE = re.compile(r"^\s*\d{1,2}:\d{1,2}:\d{1,2}\s*$")

#: Input column name -> canonical field. Only the columns a .jhd actually needs
#: are listed; everything else in the CSV (gender, spouse details, ...) is
#: ignored rather than rejected, so the same partners.csv feeds both this tool
#: and the full report pipeline.
FIELD_ALIASES = {
    "name": "name", "person": "name", "full_name": "name",
    "date_of_birth": "date_of_birth", "dob": "date_of_birth", "date": "date_of_birth",
    "time_of_birth": "time_of_birth", "tob": "time_of_birth", "time": "time_of_birth",
    "place_name": "place", "place": "place", "place_of_birth": "place",
    "location": "place", "city": "place",
    "latitude": "latitude", "lat": "latitude",
    "longitude": "longitude", "long": "longitude", "lon": "longitude", "lng": "longitude",
    "timezone": "timezone", "tz": "timezone", "timezone_offset": "timezone",
    "time_zone": "timezone", "utc_offset": "timezone",
    "country": "country",
    "output": "output", "filename": "output",
}

REQUIRED = ("date_of_birth", "time_of_birth", "place", "latitude", "longitude", "timezone")


class RowError(ValueError):
    """A row that cannot be turned into a .jhd; reported, then skipped."""


# --------------------------------------------------------------------------
# JHD encoding
# --------------------------------------------------------------------------

def _pack_dms(value: float, *, seconds: bool = True) -> str:
    """Decimal degrees/hours -> JHora packed ``D.MMSS00`` magnitude string.

    Every angular/temporal field in a .jhd is packed sexagesimal: the digits
    after the point ARE the minutes and seconds, not a fraction. 75.75 deg is
    written ``75.450000`` (75 deg 45'), not ``75.750000``. Sign is the caller's
    job. ``seconds=False`` encodes arc-minutes only, used for the timezone.
    """
    v = abs(float(value))
    d = int(v)
    minutes_full = (v - d) * 60.0
    m = int(minutes_full)
    if seconds:
        s = round((minutes_full - m) * 60.0)
    else:
        m = round(minutes_full)
        s = 0
    # normalize any rounding carry so MM < 60 and SS < 60
    if s >= 60:
        s -= 60
        m += 1
    if m >= 60:
        m -= 60
        d += 1
    return f"{d}.{m:02d}{s:02d}00"


def _time_field(time_of_birth: str) -> str:
    """Line 4: clock time packed ``H.MMSS``, printed with 15 decimals.

    Built by string construction, never ``float(...):.15f`` — that round trip
    turns 15:45 into ``15.449999999999999``, digits a positional reader sees as
    44 min 99 sec.
    """
    hh, mm, ss = (int(x) for x in time_of_birth.split(":"))
    return f"{hh}.{mm:02d}{ss:02d}00".ljust(len(str(hh)) + 1 + 15, "0")


def build_jhd(rec: dict) -> str:
    """Return the full .jhd text (CRLF-terminated) for a validated record.

    Sign conventions are JHora's own and are not the usual ones: timezone East
    of Greenwich is NEGATIVE (+5:30 -> ``-5.300000``), longitude East is
    NEGATIVE, latitude North stays positive.
    """
    year, month, day = (int(x) for x in rec["date_of_birth"].split(","))
    tz = float(rec["timezone"])
    lon = float(rec["longitude"])
    lat = float(rec["latitude"])

    tz_packed = _pack_dms(tz, seconds=False)
    tz_packed = f"-{tz_packed}" if tz >= 0 else tz_packed
    tz_decimal = f"{-tz:f}"
    lon_field = _pack_dms(lon)
    lon_field = f"-{lon_field}" if lon >= 0 else lon_field
    lat_field = _pack_dms(lat)
    lat_field = lat_field if lat >= 0 else f"-{lat_field}"

    lines = [
        str(month),
        str(day),
        str(year),
        _time_field(rec["time_of_birth"]),
        tz_packed,
        lon_field,
        lat_field,
        "0.000000",              # altitude / observer height
        # the timezone again, twice, but plain decimal hours this time
        tz_decimal,
        tz_decimal,
        "0",
        COUNTRY_INDEX,
        rec["place"],            # line 13 is the city; the person's name is
        rec["country"],          # line 14; JHora keeps the name in the FILENAME
        "1",                     # chart style flag
        "1013.250000",           # atmospheric pressure (hPa)
        "20.000000",             # temperature (C)
        "1",
    ]
    return "\r\n".join(lines) + "\r\n"


# --------------------------------------------------------------------------
# CSV -> records
# --------------------------------------------------------------------------

def normalize_row(data: dict) -> dict:
    """Map a raw CSV row onto canonical fields and validate them."""
    rec: dict = {}
    for key, value in data.items():
        if key is None:
            continue
        norm = re.sub(r"[\s\-]+", "_", str(key).strip().lower())
        field = FIELD_ALIASES.get(norm)
        if field is None or value in (None, ""):
            continue
        rec[field] = str(value).strip()

    missing = [f for f in REQUIRED if not rec.get(f)]
    if missing:
        raise RowError(f"missing required field(s): {', '.join(missing)}")

    if not _DATE_RE.match(rec["date_of_birth"]):
        raise RowError(f"date_of_birth must be 'YYYY,M,D' (got {rec['date_of_birth']!r})")
    if not _TIME_RE.match(rec["time_of_birth"]):
        raise RowError(f"time_of_birth must be 'HH:MM:SS' (got {rec['time_of_birth']!r})")

    for field in ("latitude", "longitude", "timezone"):
        try:
            rec[field] = float(rec[field])
        except (TypeError, ValueError):
            raise RowError(f"{field} must be numeric (got {rec[field]!r})") from None
    if not -90.0 <= rec["latitude"] <= 90.0:
        raise RowError(f"latitude out of range: {rec['latitude']}")
    if not -180.0 <= rec["longitude"] <= 180.0:
        raise RowError(f"longitude out of range: {rec['longitude']}")
    if not -14.0 <= rec["timezone"] <= 14.0:
        raise RowError(f"timezone out of range: {rec['timezone']}")

    rec.setdefault("name", "")
    rec["country"] = rec.get("country") or DEFAULT_COUNTRY
    return rec


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\-]+", "_", (text or "").strip())
    return text.strip("_") or "chart"


def output_stem(rec: dict) -> str:
    """Filename (no extension) for a record — this is where the name lives."""
    if rec.get("output"):
        return _slugify(Path(rec["output"]).stem)
    return f"{_slugify(rec['name'] or rec['place'])}_{rec['date_of_birth'].replace(',', '-')}"


def read_rows(csv_path: Path):
    """Yield ``(line_number, raw_dict)`` for each non-blank data row.

    ``skipinitialspace`` is what lets ``Name, "1998,9,10", x`` parse: without
    it a quoted field starting after a space is read as literal text and the
    commas inside it split the row, corrupting every later column.
    """
    with csv_path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh, skipinitialspace=True)
        if reader.fieldnames is None:
            return
        reader.fieldnames = [(n or "").strip().lower() for n in reader.fieldnames]
        for row in reader:
            cleaned = {k: v for k, v in row.items() if k is not None}
            if not any(v not in (None, "") for v in cleaned.values()):
                continue
            yield reader.line_num, cleaned


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def convert(csv_path: Path, out_dir: Path) -> tuple[int, list[str]]:
    """Write one .jhd per valid row. Returns ``(written, errors)``.

    A bad row never stops the run: it is collected and reported at the end, so
    one typo in row 3 cannot cost you rows 4-40.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    errors: list[str] = []
    used: set[str] = set()

    for line_number, raw in read_rows(csv_path):
        try:
            rec = normalize_row(raw)
        except RowError as exc:
            errors.append(f"line {line_number}: {exc}")
            continue

        stem = output_stem(rec)
        candidate, n = stem, 2
        while candidate in used:          # two people, same name and birthday
            candidate = f"{stem}_{n}"
            n += 1
        used.add(candidate)

        path = out_dir / f"{candidate}.jhd"
        # newline="" so the CRLF pairs built above survive verbatim on every OS
        with path.open("w", encoding="utf-8", newline="") as fh:
            fh.write(build_jhd(rec))
        written += 1
        print(f"  {path.name}")

    return written, errors


def _base_dir() -> Path:
    """Folder to look in for a default CSV: the .exe's own folder when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def _resolve_input(given: Path | None) -> Path:
    if given is not None:
        return given
    for candidate in (_base_dir() / DEFAULT_CSV_NAME, Path.cwd() / DEFAULT_CSV_NAME):
        if candidate.is_file():
            return candidate
    raise SystemExit(
        f"No CSV given and no {DEFAULT_CSV_NAME} found in {_base_dir()}.\n"
        f"Drag a .csv file onto this program, or put {DEFAULT_CSV_NAME} beside it."
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="JhdFromCsv",
        description="Generate Jagannatha Hora .jhd files from a CSV of birth details.",
    )
    parser.add_argument("input", nargs="?", type=Path,
                        help=f"CSV file. Defaults to {DEFAULT_CSV_NAME} beside this program. "
                             "Columns: name, date_of_birth (YYYY,M,D), time_of_birth "
                             "(HH:MM:SS), place, latitude, longitude, timezone.")
    parser.add_argument("-o", "--out-dir", type=Path, default=None,
                        help=f"Output folder (default: a '{DEFAULT_OUT_DIRNAME}' folder "
                             "next to the CSV).")
    parser.add_argument("--no-pause", action="store_true",
                        help="Don't wait for a keypress on exit (for scripted runs).")
    args = parser.parse_args(argv)

    # Frozen builds are usually double-clicked or drag-dropped, and the console
    # window dies with the process — hold it open so the output is readable.
    pause = getattr(sys, "frozen", False) and not args.no_pause
    status = 0
    try:
        csv_path = _resolve_input(args.input)
        if not csv_path.is_file():
            raise SystemExit(f"Input file not found: {csv_path}")

        out_dir = args.out_dir or csv_path.resolve().parent / DEFAULT_OUT_DIRNAME
        print(f"Reading {csv_path}")
        print(f"Writing {out_dir}")
        written, errors = convert(csv_path, out_dir)

        print(f"\n{written} .jhd file(s) written to {out_dir}")
        if errors:
            print(f"{len(errors)} row(s) skipped:")
            for message in errors:
                print(f"  {message}")
            status = 1
        elif written == 0:
            print("No usable rows found — check the CSV's header row.")
            status = 1
    except SystemExit as exc:
        # SystemExit carries either our own message string or argparse's numeric
        # code (argparse has already printed its own error by then).
        if isinstance(exc.code, str):
            print(f"\n{exc.code}", file=sys.stderr)
            status = 2
        else:
            status = exc.code or 0
    finally:
        if pause:
            try:
                input("\nPress Enter to close...")
            except (EOFError, KeyboardInterrupt):
                pass
    return status


if __name__ == "__main__":
    sys.exit(main())
