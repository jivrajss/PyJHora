"""Tests for the standalone exe tool.

The important one is ``test_matches_pyjhora_batch_writer``: this tool duplicates
the JHD encoding instead of importing it (so the frozen exe stays dependency
free), and this is what stops the two copies drifting apart.

Run:  python -m pytest tools/test_jhd_from_csv.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jhd_from_csv as tool  # noqa: E402

# The verified reference chart from the .jhd format work: 15 Jun 1985,
# 10:30:00, Ujjain, 23.5N 75.75E, +5:30.
REFERENCE_ROW = {
    "name": "Reference Chart",
    "date_of_birth": "1985,6,15",
    "time_of_birth": "10:30:00",
    "place": "Ujjain",
    "latitude": "23.5",
    "longitude": "75.75",
    "timezone": "5.5",
}

CSV_TEXT = (
    "name,date_of_birth,time_of_birth,place,latitude,longitude,timezone,gender\n"
    'Reference Chart,"1985,6,15",10:30:00,Ujjain,23.5,75.75,5.5,male\n'
    'Spaced Quote, "2001,11,3",07:15:00,"Nagpur, Maharashtra",21.1458,79.0882,5.5, male\n'
)


def _lines(text: str) -> list[str]:
    assert text.endswith("\r\n")
    assert "\r\n" in text and "\n\r" not in text
    return text.strip("\r\n").split("\r\n")


def test_reference_chart_encoding():
    """Every field of the byte-verified reference export."""
    lines = _lines(tool.build_jhd(tool.normalize_row(REFERENCE_ROW)))
    assert lines[0:3] == ["6", "15", "1985"]
    assert lines[3] == "10.300000000000000"      # packed H.MMSS, 15 decimals
    assert lines[4] == "-5.300000"               # tz packed, East negative
    assert lines[5] == "-75.450000"              # 75.75 deg -> 75 deg 45', East negative
    assert lines[6] == "23.300000"               # 23.5 deg -> 23 deg 30', North positive
    assert lines[7] == "0.000000"
    assert lines[8] == lines[9] == "-5.500000"   # the decimal-hours exception
    assert lines[10] == "0"
    assert lines[11] == "105"
    assert lines[12] == "Ujjain"
    assert lines[13] == "India"                  # name is never in the file
    assert lines[14:] == ["1", "1013.250000", "20.000000", "1"]
    assert len(lines) == 18


def test_time_is_string_built_not_float_rounded():
    """15:45 must not come back as 15.449999999999999 (44 min, 99 sec)."""
    assert tool._time_field("15:45:00") == "15.450000000000000"
    assert tool._time_field("09:07:00") == "9.070000000000000"
    assert tool._time_field("3:00:00") == "3.000000000000000"


def test_packing_carry_normalizes():
    """Rounding must never emit 60 minutes or 60 seconds."""
    assert tool._pack_dms(26.999999) == "27.000000"
    assert tool._pack_dms(27.99999) == "28.000000"


def test_western_hemisphere_signs():
    """Longitude West is positive here, and timezone West of Greenwich too."""
    row = dict(REFERENCE_ROW, latitude="-33.75", longitude="-70.5", timezone="-4")
    lines = _lines(tool.build_jhd(tool.normalize_row(row)))
    assert lines[4] == "4.000000"        # UTC-4 -> positive
    assert lines[5] == "70.300000"       # 70.5 W -> positive
    assert lines[6] == "-33.450000"      # 33.75 S -> negative
    assert lines[8] == "4.000000"


def test_column_aliases_and_ignored_columns():
    rec = tool.normalize_row({
        "Full Name": "Alias Person", "DOB": "2001,11,3", "TOB": "07:15:00",
        "location": "Nagpur", "lat": "21.1458", "lng": "79.0882",
        "utc_offset": "5.5", "gender": "male", "spouse_dob": "1991,1,1",
    })
    assert rec["name"] == "Alias Person"
    assert rec["latitude"] == pytest.approx(21.1458)
    assert rec["timezone"] == 5.5


@pytest.mark.parametrize("bad, message", [
    ({"date_of_birth": "3/11/2001"}, "date_of_birth"),
    ({"time_of_birth": "3.15 pm"}, "time_of_birth"),
    ({"latitude": "north"}, "latitude"),
    ({"latitude": "99"}, "out of range"),
    ({"timezone": ""}, "missing required"),
])
def test_invalid_rows_rejected(bad, message):
    with pytest.raises(tool.RowError, match=message):
        tool.normalize_row(dict(REFERENCE_ROW, **bad))


def test_output_stem():
    rec = tool.normalize_row(REFERENCE_ROW)
    assert tool.output_stem(rec) == "Reference_Chart_1985-6-15"
    assert tool.output_stem(dict(rec, output="custom.jhd")) == "custom"


def test_convert_end_to_end(tmp_path):
    csv_path = tmp_path / "partners.csv"
    csv_path.write_text(CSV_TEXT, encoding="utf-8")
    out_dir = tmp_path / "jhd"

    written, errors = tool.convert(csv_path, out_dir)
    assert (written, errors) == (2, [])

    names = sorted(p.name for p in out_dir.glob("*.jhd"))
    assert names == ["Reference_Chart_1985-6-15.jhd", "Spaced_Quote_2001-11-3.jhd"]
    # newline="" so Python's universal-newline translation doesn't hide a
    # missing CR — the CRLF endings are part of the format.
    with (out_dir / "Spaced_Quote_2001-11-3.jhd").open(newline="") as fh:
        raw = fh.read()
    # the space-before-quote row must not have been split across columns
    assert _lines(raw)[12] == "Nagpur, Maharashtra"


def test_bad_row_does_not_abort_the_run(tmp_path):
    csv_path = tmp_path / "partners.csv"
    csv_path.write_text(CSV_TEXT + 'Broken,3/11/2001,07:15:00,X,21,79,5.5,male\n',
                        encoding="utf-8")
    written, errors = tool.convert(csv_path, tmp_path / "jhd")
    assert written == 2
    assert len(errors) == 1 and "date_of_birth" in errors[0]


def test_duplicate_names_get_distinct_files(tmp_path):
    csv_path = tmp_path / "partners.csv"
    row = 'Twin,"1985,6,15",10:30:00,Ujjain,23.5,75.75,5.5,male\n'
    csv_path.write_text(CSV_TEXT.splitlines()[0] + "\n" + row + row, encoding="utf-8")
    written, _ = tool.convert(csv_path, tmp_path / "jhd")
    assert written == 2
    assert sorted(p.name for p in (tmp_path / "jhd").glob("*.jhd")) == \
        ["Twin_1985-6-15.jhd", "Twin_1985-6-15_2.jhd"]


def test_matches_pyjhora_batch_writer():
    """Byte-identical to the pipeline's writer — the anti-drift check.

    Skipped rather than failed where pyjhora_batch can't be imported (it pulls
    in PyQt), because this tool must stay usable without those dependencies.
    """
    try:
        from pyjhora_batch.jhd_writer import build_jhd as reference_build
        from pyjhora_batch.wrapper import BirthRecord
    except Exception as exc:                      # pragma: no cover
        pytest.skip(f"pyjhora_batch unavailable: {exc}")

    rows = [
        REFERENCE_ROW,
        dict(REFERENCE_ROW, date_of_birth="2001,11,3", time_of_birth="07:15:00",
             place="Nagpur, Maharashtra", latitude="21.1458",
             longitude="79.0882"),
        dict(REFERENCE_ROW, time_of_birth="04:54:00", latitude="12.9716",
             longitude="77.5946"),
        dict(REFERENCE_ROW, latitude="-33.75", longitude="-70.5", timezone="-4",
             place="Santiago"),
    ]
    for row in rows:
        mine = tool.build_jhd(tool.normalize_row(row))
        theirs = reference_build(BirthRecord(
            date_of_birth=row["date_of_birth"], time_of_birth=row["time_of_birth"],
            place_name=row["place"], latitude=float(row["latitude"]),
            longitude=float(row["longitude"]), timezone=float(row["timezone"]),
            name=row["name"],
        ))
        assert mine == theirs, f"diverged on {row['date_of_birth']} {row['place']}"
