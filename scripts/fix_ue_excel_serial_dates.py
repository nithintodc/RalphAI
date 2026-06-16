#!/usr/bin/env python3
"""
Fix Uber Eats CSV rows where Excel converted dates/times to serial numbers.

Excel 1900 date system (Windows default):
  - Order date / Payout date: integer serial (e.g. 45748 -> 4/1/2025)
  - Order Accept Time: fraction of day (e.g. 0.984028 -> 11:37 PM)

Usage:
  python scripts/fix_ue_excel_serial_dates.py path/to/UE-export.csv
  python scripts/fix_ue_excel_serial_dates.py path/to/file.csv --in-place
  python scripts/fix_ue_excel_serial_dates.py path/to/file.csv -o path/to/fixed.csv --dry-run
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Excel serial 1 = 1900-01-01; epoch for day math is 1899-12-30.
EXCEL_EPOCH = datetime(1899, 12, 30)
SLASH_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
SERIAL_DATE_RE = re.compile(r"^\d{4,5}(\.0+)?$")
SERIAL_TIME_RE = re.compile(r"^0\.\d+$|^\d+\.\d+$")

DATE_COLUMNS = ("Order date", "Payout Date")
TIME_COLUMNS = ("Order Accept Time",)


def excel_serial_to_date(serial: float) -> datetime:
    days = int(serial)
    return EXCEL_EPOCH + timedelta(days=days)


def format_ue_date(dt: datetime) -> str:
    """Match existing UE export style: M/D/YYYY (no zero-padding)."""
    return f"{dt.month}/{dt.day}/{dt.year}"


def excel_serial_to_time_str(serial: float) -> str:
    """Fraction of 24h day -> e.g. 11:37 PM."""
    total_seconds = round(serial * 86400)
    hours = (total_seconds // 3600) % 24
    minutes = (total_seconds % 3600) // 60
    period = "AM" if hours < 12 else "PM"
    display_hour = hours % 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour}:{minutes:02d} {period}"


def is_excel_serial_date(value: str) -> bool:
    text = value.strip()
    if not SERIAL_DATE_RE.match(text):
        return False
    n = float(text)
    # Roughly 1950-2060 in Excel serial space.
    return 18000 <= n <= 65000


def is_excel_serial_time(value: str) -> bool:
    text = value.strip()
    if not text or SLASH_DATE_RE.match(text) or ":" in text:
        return False
    if not SERIAL_TIME_RE.match(text):
        return False
    n = float(text)
    return 0 <= n < 1


def convert_cell(column: str, value: str) -> tuple[str, bool]:
    text = (value or "").strip()
    if not text:
        return value, False

    if column in DATE_COLUMNS and is_excel_serial_date(text):
        return format_ue_date(excel_serial_to_date(float(text))), True

    if column in TIME_COLUMNS and is_excel_serial_time(text):
        return excel_serial_to_time_str(float(text)), True

    return value, False


def find_header_row(rows: list[list[str]]) -> int:
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Store Name":
            return i
    raise ValueError("Could not find UE header row (expected 'Store Name' in column A)")


def fix_csv(
    input_path: Path,
    output_path: Path,
    *,
    dry_run: bool = False,
) -> dict:
    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        raise ValueError(f"{input_path} has no data rows")

    header_idx = find_header_row(rows)
    header = rows[header_idx]
    col_index = {name: idx for idx, name in enumerate(header)}

    missing = [c for c in (*DATE_COLUMNS, *TIME_COLUMNS) if c not in col_index]
    if missing:
        raise ValueError(f"Missing expected columns: {', '.join(missing)}")

    stats = {
        "date_cells_fixed": 0,
        "time_cells_fixed": 0,
        "rows_touched": 0,
    }
    fix_columns = set(DATE_COLUMNS) | set(TIME_COLUMNS)

    for row in rows[header_idx + 1 :]:
        row_changed = False
        for col in fix_columns:
            idx = col_index[col]
            if idx >= len(row):
                continue
            new_value, changed = convert_cell(col, row[idx])
            if changed:
                row[idx] = new_value
                row_changed = True
                if col in DATE_COLUMNS:
                    stats["date_cells_fixed"] += 1
                else:
                    stats["time_cells_fixed"] += 1
        if row_changed:
            stats["rows_touched"] += 1

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="UE financial CSV to fix")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path (default: <input>.fixed.csv, or input path with --in-place)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite input file (creates .bak backup first)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts only; do not write output",
    )
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    if args.in_place:
        output_path = input_path
    elif args.output:
        output_path = args.output.expanduser().resolve()
    else:
        output_path = input_path.with_name(f"{input_path.stem}.fixed{input_path.suffix}")

    try:
        stats = fix_csv(input_path, output_path, dry_run=args.dry_run)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Input:  {input_path}")
    if args.dry_run:
        print("Mode:   dry-run (no file written)")
    else:
        if args.in_place and not args.dry_run:
            backup = input_path.with_suffix(input_path.suffix + ".bak")
            shutil.copy2(input_path, backup)
            print(f"Backup: {backup}")
        print(f"Output: {output_path}")
    print(f"Rows updated:      {stats['rows_touched']}")
    print(f"Date cells fixed:  {stats['date_cells_fixed']}")
    print(f"Time cells fixed:  {stats['time_cells_fixed']}")

    # Sample conversions for sanity check
    print("\nSerial reference:")
    for serial in (45747, 45748, 45749, 45807):
        print(f"  {serial} -> {format_ue_date(excel_serial_to_date(serial))}")
    print(f"  0.984028 -> {excel_serial_to_time_str(0.984027778)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
