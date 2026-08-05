# JhdFromCsv

Turns a CSV of birth details into Jagannatha Hora `.jhd` files — one per row,
ready to open in JHora. No Python, no install, nothing else needed.

## Use it

Any of these work:

1. **Drag and drop** — drag `partners.csv` onto `JhdFromCsv.exe`.
2. **Double-click** — put `partners.csv` in the same folder as the exe and
   double-click the exe.
3. **Command line** — `JhdFromCsv.exe partners.csv -o somewhere\else`

Files land in a `jhd` folder next to the CSV. The window lists every file it
writes and stays open until you press Enter.

## The CSV

The first row must be a header. `partners.example.csv` is a working sample.

| Column | Required | Example | Notes |
|---|---|---|---|
| `name` | no | `Reference Chart` | Becomes the filename — JHora stores the name nowhere else |
| `date_of_birth` | **yes** | `"1985,6,15"` | `YYYY,M,D`. Quote it, or the commas split the row |
| `time_of_birth` | **yes** | `10:30:00` | `HH:MM:SS`, 24-hour |
| `place` | **yes** | `Ujjain` | Free text; quote it if it contains commas |
| `latitude` | **yes** | `23.5` | Decimal degrees, South negative |
| `longitude` | **yes** | `75.75` | Decimal degrees, West negative |
| `timezone` | **yes** | `5.5` | Hours from UTC, so India is `5.5` |
| `country` | no | `India` | Defaults to India |
| `output` | no | `my_chart` | Overrides the generated filename |

Common alternative headers are accepted (`dob`, `tob`, `lat`, `lng`,
`utc_offset`, `place_of_birth`, ...), and any extra columns — `gender`, spouse
details, notes — are ignored, so the same file can also feed the full report
pipeline. Latitude/longitude go in as **decimal degrees**; the packed
sexagesimal form JHora wants is handled for you.

Output filenames are `Name_YYYY-M-D.jhd`. Two identical ones get `_2` appended.

## When a row is bad

Bad rows are skipped, not fatal — the run finishes, then lists what it skipped
and why (`line 4: date_of_birth must be 'YYYY,M,D' (got '18/4/1990')`). Fix
those rows and run it again. Exit code is 0 on a clean run, 1 if anything was
skipped.

## Building it on Windows

PyInstaller cannot cross-compile, so the exe has to be built on Windows. Two
ways, both producing the same file:

**1. Build it yourself** — clone the repo, then double-click
`tools\build_exe.bat`. It checks for Python, installs PyInstaller, runs the
tests, builds, and smoke-tests the result. You end up with
`dist\JhdFromCsv.exe`. The only prerequisite is Python 3.9+ on PATH
(<https://www.python.org/downloads/> — tick "Add python.exe to PATH").

**2. Let GitHub build it** — no Python needed at all. On the repo's **Actions**
tab: **Build JhdFromCsv.exe** -> **Run workflow**, wait ~1 minute, then
download the `JhdFromCsv-windows` artifact (a zip containing the exe, this
README and the sample CSV).

The exe is not code-signed, so the first launch shows a Windows SmartScreen
warning — **More info** -> **Run anyway**.

Source is `tools/jhd_from_csv.py`, standard library only. It duplicates the JHD
encoding from `pyjhora_batch/jhd_writer.py` so the exe needs no dependencies;
`tools/test_jhd_from_csv.py` fails if the two ever diverge — run it after
touching either file.
