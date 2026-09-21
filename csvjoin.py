"""csvjoin — CSV JOIN CLI.

Join two CSV files by key columns: inner, left, right, and full outer joins.
Zero runtime dependencies beyond the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class JoinResult:
    headers: list[str]
    rows: list[list[str]]
    left_count: int
    right_count: int
    joined_count: int


# ---------------------------------------------------------------------------
# CSV I/O helpers
# ---------------------------------------------------------------------------


def _open_input(path: str | None) -> Any:
    """Open a file path, stdin ("-"), or the default (stdin)."""
    if path is None or path == "-":
        return sys.stdin
    return open(path, newline="", encoding="utf-8")


def _read_csv(
    path: str | None,
    delimiter: str,
    has_header: bool = True,
) -> tuple[list[str], list[list[str]]]:
    """Read a CSV and return (headers, rows)."""
    fh = _open_input(path)
    try:
        reader = csv.reader(fh, delimiter=delimiter)
        if has_header:
            try:
                headers = next(reader)
            except StopIteration:
                return [], []
        else:
            headers = []
        rows: list[list[str]] = []
        for row in reader:
            rows.append(row)
        return headers, rows
    finally:
        if path is not None and path != "-":
            fh.close()


def _open_output(path: str | None) -> Any:
    if path is None or path == "-":
        return sys.stdout
    return open(path, "w", newline="", encoding="utf-8")


def _write_csv(
    headers: list[str],
    rows: list[list[str]],
    delimiter: str,
    path: str | None,
) -> None:
    """Write CSV to a file path or stdout."""
    out = _open_output(path)
    try:
        writer = csv.writer(out, delimiter=delimiter)
        if headers:
            writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
    finally:
        if path is not None and path != "-":
            out.close()


# ---------------------------------------------------------------------------
# Join logic: index + merge
# ---------------------------------------------------------------------------


def _build_index(
    rows: list[list[str]],
    headers: list[str],
    key_cols: list[int],
) -> dict[tuple[str, ...], list[int]]:
    """Map key tuple -> list of row indices (handles duplicate keys)."""
    index: dict[tuple[str, ...], list[int]] = {}
    for i, row in enumerate(rows):
        key = tuple(row[c] for c in key_cols)
        index.setdefault(key, []).append(i)
    return index


def _non_key_headers(headers: list[str], key_cols: list[int]) -> list[str]:
    """Return header names excluding key columns."""
    key_set = set(key_cols)
    return [h for i, h in enumerate(headers) if i not in key_set]


def join_csv(
    left_headers: list[str],
    left_rows: list[list[str]],
    right_headers: list[str],
    right_rows: list[list[str]],
    key_left: list[int],
    key_right: list[int],
    join_type: str,
    missing: str,
) -> JoinResult:
    """Perform the join and return result metadata + rows."""
    left_index = _build_index(left_rows, left_headers, key_left)
    right_index = _build_index(right_rows, right_headers, key_right)

    non_key_left = _non_key_headers(left_headers, key_left)
    non_key_right = _non_key_headers(right_headers, key_right)

    # Output headers: shared keys (from left) + non-key left + non-key right
    # Deduplicate non-key column names to avoid collisions
    seen: set[str] = set()
    headers: list[str] = []
    key_headers: list[str] = []

    for i in key_left:
        name = left_headers[i]
        key_headers.append(name)
        headers.append(name)
        seen.add(name)

    for name in non_key_left:
        if name in seen:
            name = f"{name}_x"
        headers.append(name)
        seen.add(name)

    for name in non_key_right:
        if name in seen:
            name = f"{name}_y"
        headers.append(name)
        seen.add(name)

    rows: list[list[str]] = []
    left_count = len(left_rows)
    right_count = len(right_rows)
    joined_count = 0

    left_keys = set(left_index.keys())
    right_keys = set(right_index.keys())

    key_left_set = set(key_left)
    key_right_set = set(key_right)

    def _emit_row(li: int | None, ri: int | None, key: tuple[str, ...]) -> None:
        nonlocal joined_count
        joined_count += 1
        row: list[str] = []
        if key_headers:
            row.extend(key)
        if li is not None:
            row.extend(
                left_rows[li][i]
                for i in range(len(left_headers))
                if i not in key_left_set
            )
        else:
            row.extend([missing] * len(non_key_left))
        if ri is not None:
            row.extend(
                right_rows[ri][i]
                for i in range(len(right_headers))
                if i not in key_right_set
            )
        else:
            row.extend([missing] * len(non_key_right))
        rows.append(row)

    if join_type == "inner":
        common = left_keys & right_keys
        for key in sorted(common):
            for li in left_index[key]:
                for ri in right_index[key]:
                    _emit_row(li, ri, key)

    elif join_type == "left":
        for key in sorted(left_keys):
            l_indices = left_index[key]
            r_indices = right_index.get(key, [])
            if r_indices:
                for li in l_indices:
                    for ri in r_indices:
                        _emit_row(li, ri, key)
            else:
                for li in l_indices:
                    _emit_row(li, None, key)

    elif join_type == "right":
        for key in sorted(right_keys):
            r_indices = right_index[key]
            l_indices = left_index.get(key, [])
            if l_indices:
                for li in l_indices:
                    for ri in r_indices:
                        _emit_row(li, ri, key)
            else:
                for ri in r_indices:
                    _emit_row(None, ri, key)

    elif join_type == "full":
        all_keys = left_keys | right_keys
        for key in sorted(all_keys):
            l_indices = left_index.get(key, [])
            r_indices = right_index.get(key, [])
            if l_indices and r_indices:
                for li in l_indices:
                    for ri in r_indices:
                        _emit_row(li, ri, key)
            elif l_indices:
                for li in l_indices:
                    _emit_row(li, None, key)
            else:
                for ri in r_indices:
                    _emit_row(None, ri, key)
    else:
        raise ValueError(f"Unknown join type: {join_type}")

    return JoinResult(
        headers=headers,
        rows=rows,
        left_count=left_count,
        right_count=right_count,
        joined_count=joined_count,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="csvjoin",
        description="Join two CSV files by key columns.",
    )
    parser.add_argument(
        "left",
        nargs="?",
        default=None,
        help="Left CSV file path (or - for stdin)",
    )
    parser.add_argument(
        "right",
        nargs="?",
        default=None,
        help="Right CSV file path (or - for stdin)",
    )

    key_group = parser.add_argument_group("key columns")
    key_group.add_argument(
        "--key",
        "-k",
        nargs="+",
        action="append",
        dest="keys",
        metavar="COL",
        help=(
            "Key column(s). First occurrence = left file, "
            "second = right file. Can be specified once "
            "(shared key names) or twice."
        ),
    )

    type_group = parser.add_argument_group("join type")
    type_group.add_argument(
        "--type",
        "-t",
        choices=["inner", "left", "right", "full"],
        default="inner",
        help="Join type (default: inner)",
    )

    io_group = parser.add_argument_group("I/O options")
    io_group.add_argument(
        "--delimiter",
        "-d",
        default=",",
        help="Input field delimiter (default: ,)",
    )
    io_group.add_argument(
        "--output-delimiter",
        "-oD",
        default=None,
        help="Output field delimiter (default: same as input)",
    )
    io_group.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: stdout)",
    )
    io_group.add_argument(
        "--no-header",
        action="store_true",
        default=False,
        help="Treat input as headerless; generate c0, c1, ... headers",
    )
    io_group.add_argument(
        "--missing",
        "-m",
        default="",
        help="Value to use for missing fields in outer joins (default: empty string)",
    )
    io_group.add_argument(
        "--format",
        choices=["csv", "summary"],
        default="csv",
        help="Output format: csv (default) or summary",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    key_left_names: list[str]
    key_right_names: list[str]

    # --- read inputs first (needed for key name resolution) ---
    try:
        left_headers, left_rows = _read_csv(args.left, args.delimiter, not args.no_header)
    except FileNotFoundError:
        print(f"Error: cannot open '{args.left}'", file=sys.stderr)
        return 2
    try:
        right_headers, right_rows = _read_csv(args.right, args.delimiter, not args.no_header)
    except FileNotFoundError:
        print(f"Error: cannot open '{args.right}'", file=sys.stderr)
        return 2

    if args.no_header:
        left_headers = [f"c{i}" for i in range(len(left_rows[0]))] if left_rows else []
        right_headers = [f"c{i}" for i in range(len(right_rows[0]))] if right_rows else []

    if not left_headers:
        print("Error: left CSV has no columns", file=sys.stderr)
        return 2
    if not right_headers:
        print("Error: right CSV has no columns", file=sys.stderr)
        return 2

    # --- resolve keys (now headers are available) ---
    keys_raw: list[list[str]] | None = args.keys
    if keys_raw is None:
        print("--key is required", file=sys.stderr)
        return 2

    if len(keys_raw) == 1:
        all_keys = keys_raw[0]
        if len(all_keys) == 1:
            key_left_names = all_keys
            key_right_names = all_keys
        else:
            # Try treating all as shared keys first; fall back to split
            left_has_all = all(k in left_headers for k in all_keys)
            right_has_all = all(k in right_headers for k in all_keys)
            if left_has_all and right_has_all:
                key_left_names = all_keys
                key_right_names = all_keys
            else:
                mid = len(all_keys) // 2
                if mid == 0:
                    print(
                        "--key requires at least 2 column names "
                        "for left/right when using a single --key flag",
                        file=sys.stderr,
                    )
                    return 2
                key_left_names = all_keys[:mid]
                key_right_names = all_keys[mid:]
    elif len(keys_raw) >= 2:
        key_left_names = keys_raw[0]
        key_right_names = keys_raw[1]

    output_delimiter = args.output_delimiter or args.delimiter

    # --- resolve key column indices ---
    key_left_idx: list[int] = []
    for name in key_left_names:
        if name not in left_headers:
            print(f"Error: left key column '{name}' not found in left CSV headers", file=sys.stderr)
            return 2
        key_left_idx.append(left_headers.index(name))

    key_right_idx: list[int] = []
    for name in key_right_names:
        if name not in right_headers:
            msg = (
                f"Error: right key column '{name}' not found "
                "in right CSV headers"
            )
            print(msg, file=sys.stderr)
            return 2
        key_right_idx.append(right_headers.index(name))

    if len(key_left_idx) != len(key_right_idx):
        msg = (
            f"Error: left has {len(key_left_idx)} key columns, "
            f"right has {len(key_right_idx)}; they must match"
        )
        print(msg, file=sys.stderr)
        return 2

    # --- perform join ---
    result = join_csv(
        left_headers=left_headers,
        left_rows=left_rows,
        right_headers=right_headers,
        right_rows=right_rows,
        key_left=key_left_idx,
        key_right=key_right_idx,
        join_type=args.type,
        missing=args.missing,
    )

    # --- output ---
    if args.format == "summary":
        print(f"Left:  {result.left_count} row(s)")
        print(f"Right: {result.right_count} row(s)")
        print(f"Joined: {result.joined_count} row(s)")
        if result.headers:
            print(f"Output columns: {len(result.headers)}")
            print(f"  {', '.join(result.headers)}")
    else:
        _write_csv(result.headers, result.rows, output_delimiter, args.output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
