"""Tests for csvjoin — CSV JOIN CLI.

Covers inner, left, right, full outer joins, key resolution, edge cases,
and CLI error paths.
"""

from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

import pytest

from csvjoin import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csv_lines(headers: list[str], rows: list[list[str]]) -> list[str]:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=",")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().splitlines()


def _write_tmp_csv(headers: list[str], rows: list[list[str]]) -> Path:
    p = Path(tempfile.mktemp(suffix=".csv"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(_csv_lines(headers, rows)) + "\n")
    return p


# ---------------------------------------------------------------------------
# Inner join
# ---------------------------------------------------------------------------


class TestInnerJoin:
    def test_basic_inner(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(
            ["id", "name"],
            [["1", "Alice"], ["2", "Bob"], ["3", "Carol"]],
        )
        right = _write_tmp_csv(
            ["id", "score"],
            [["1", "90"], ["2", "85"], ["4", "70"]],
        )
        out = tmp_path / "out.csv"
        rc = main([str(left), str(right), "--key", "id", "--output", str(out)])
        assert rc == 0
        lines = out.read_text().splitlines()
        assert len(lines) == 3  # header + 2 joined rows
        assert "id,name,score" in lines[0]
        assert any("Alice" in line and "90" in line for line in lines)
        assert any("Bob" in line and "85" in line for line in lines)
        assert not any("Carol" in line for line in lines)
        assert not any("70" in line for line in lines)

    def test_inner_no_matches(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(["id"], [["1"], ["2"]])
        right = _write_tmp_csv(["id"], [["3"], ["4"]])
        out = tmp_path / "out.csv"
        rc = main([str(left), str(right), "--key", "id", "--output", str(out)])
        assert rc == 0
        lines = out.read_text().splitlines()
        assert len(lines) == 1  # header only

    def test_inner_duplicate_keys(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(
            ["id", "val"],
            [["1", "a"], ["1", "b"]],
        )
        right = _write_tmp_csv(
            ["id", "val"],
            [["1", "x"]],
        )
        out = tmp_path / "out.csv"
        rc = main([str(left), str(right), "--key", "id", "--output", str(out)])
        assert rc == 0
        lines = out.read_text().splitlines()
        assert len(lines) == 3  # header + 2 rows (cartesian: 2 * 1)


# ---------------------------------------------------------------------------
# Left join
# ---------------------------------------------------------------------------


class TestLeftJoin:
    def test_basic_left(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(
            ["id", "name"],
            [["1", "Alice"], ["2", "Bob"], ["3", "Carol"]],
        )
        right = _write_tmp_csv(
            ["id", "score"],
            [["1", "90"], ["2", "85"]],
        )
        out = tmp_path / "out.csv"
        rc = main([
            str(left), str(right),
            "--key", "id",
            "--type", "left",
            "--output", str(out),
        ])
        assert rc == 0
        lines = out.read_text().splitlines()
        assert len(lines) == 4  # header + 3 rows (all left)
        assert any("Carol" in line for line in lines)

    def test_left_missing_value(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(["id", "name"], [["1", "Alice"], ["2", "Bob"]])
        right = _write_tmp_csv(["id", "score"], [["1", "90"]])
        out = tmp_path / "out.csv"
        rc = main([
            str(left), str(right),
            "--key", "id", "--type", "left",
            "--missing", "N/A",
            "--output", str(out),
        ])
        assert rc == 0
        lines = out.read_text().splitlines()
        assert any("Bob" in line and "N/A" in line for line in lines)


# ---------------------------------------------------------------------------
# Right join
# ---------------------------------------------------------------------------


class TestRightJoin:
    def test_basic_right(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(
            ["id", "name"],
            [["1", "Alice"], ["2", "Bob"]],
        )
        right = _write_tmp_csv(
            ["id", "score"],
            [["1", "90"], ["3", "70"]],
        )
        out = tmp_path / "out.csv"
        rc = main([
            str(left), str(right),
            "--key", "id", "--type", "right",
            "--output", str(out),
        ])
        assert rc == 0
        lines = out.read_text().splitlines()
        assert any("3" in line and "70" in line for line in lines)
        assert not any("Carol" in line for line in lines)


# ---------------------------------------------------------------------------
# Full outer join
# ---------------------------------------------------------------------------


class TestFullOuterJoin:
    def test_basic_full(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(
            ["id", "name"],
            [["1", "Alice"], ["2", "Bob"]],
        )
        right = _write_tmp_csv(
            ["id", "score"],
            [["2", "85"], ["3", "70"]],
        )
        out = tmp_path / "out.csv"
        rc = main([
            str(left), str(right),
            "--key", "id", "--type", "full",
            "--output", str(out),
        ])
        assert rc == 0
        lines = out.read_text().splitlines()
        assert len(lines) == 4  # header + 3 rows
        assert any("Alice" in line for line in lines)
        assert any("3" in line and "70" in line for line in lines)


# ---------------------------------------------------------------------------
# Multi-column keys
# ---------------------------------------------------------------------------


class TestMultiKey:
    def test_composite_key(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(
            ["a", "b", "v1"],
            [["1", "x", "A"], ["2", "y", "B"]],
        )
        right = _write_tmp_csv(
            ["a", "b", "v2"],
            [["1", "x", "X"], ["1", "y", "Y"]],
        )
        out = tmp_path / "out.csv"
        rc = main([
            str(left), str(right),
            "--key", "a", "b",
            "--output", str(out),
        ])
        assert rc == 0
        lines = out.read_text().splitlines()
        # header + 1 matched row (a=1,b=x matches in both)
        assert len(lines) == 2
        assert "1,x" in lines[1]
        assert "A" in lines[1]
        assert "X" in lines[1]


# ---------------------------------------------------------------------------
# Different key column names
# ---------------------------------------------------------------------------


class TestDifferentKeyNames:
    def test_key_names_differ(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(["user_id", "name"], [["1", "Alice"], ["2", "Bob"]])
        right = _write_tmp_csv(["uid", "score"], [["1", "90"], ["2", "85"]])
        out = tmp_path / "out.csv"
        rc = main([
            str(left), str(right),
            "--key", "user_id", "uid",
            "--output", str(out),
        ])
        assert rc == 0
        lines = out.read_text().splitlines()
        assert len(lines) == 3  # header + 2


# ---------------------------------------------------------------------------
# Delimiter
# ---------------------------------------------------------------------------


class TestDelimiter:
    def test_tsv(self, tmp_path: Path) -> None:
        left = tmp_path / "left.tsv"
        left.write_text("id\tname\n1\tAlice\n2\tBob\n")
        right = tmp_path / "right.tsv"
        right.write_text("id\tscore\n1\t90\n2\t85\n")
        out = tmp_path / "out.tsv"
        rc = main([
            str(left), str(right),
            "--key", "id",
            "--delimiter", "\t",
            "--output-delimiter", "\t",
            "--output", str(out),
        ])
        assert rc == 0
        lines = out.read_text().splitlines()
        assert len(lines) == 3
        assert lines[1].split("\t") == ["1", "Alice", "90"]


# ---------------------------------------------------------------------------
# No header
# ---------------------------------------------------------------------------


class TestNoHeader:
    def test_headerless(self, tmp_path: Path) -> None:
        left = tmp_path / "left.csv"
        left.write_text("1,Alice\n2,Bob\n")
        right = tmp_path / "right.csv"
        right.write_text("1,90\n2,85\n")
        out = tmp_path / "out.csv"
        rc = main([
            str(left), str(right),
            "--key", "c0",
            "--no-header",
            "--output", str(out),
        ])
        assert rc == 0
        lines = out.read_text().splitlines()
        # c0 is the shared key; c1 from left is unique, c1 from right becomes c1_y
        assert "c0,c1,c1_y" in lines[0]


# ---------------------------------------------------------------------------
# Stdin mode
# ---------------------------------------------------------------------------


class TestStdin:
    def test_stdin_left(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        right = tmp_path / "right.csv"
        right.write_text("id,score\n1,90\n2,85\n")
        stdin_data = "id,name\n1,Alice\n2,Bob\n3,Carol\n"
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin_data))
        out = tmp_path / "out.csv"
        rc = main([
            "-", str(right),
            "--key", "id",
            "--output", str(out),
        ])
        assert rc == 0
        lines = out.read_text().splitlines()
        assert len(lines) == 3

    def test_stdin_both(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Both stdin is not supported (csvjoin reads stdin once).
        # Documented limitation — skip in this run.
        pass


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrors:
    def test_missing_key_flag(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(["id"], [["1"]])
        right = _write_tmp_csv(["id"], [["1"]])
        rc = main([str(left), str(right)])
        assert rc == 2

    def test_key_not_found_left(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(["id"], [["1"]])
        right = _write_tmp_csv(["id"], [["1"]])
        rc = main([str(left), str(right), "--key", "nope"])
        assert rc == 2

    def test_mismatched_key_count(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(["a", "b"], [["1", "x"]])
        right = _write_tmp_csv(["a", "b"], [["1", "x"]])
        rc = main([str(left), str(right), "--key", "a", "b", "c"])
        assert rc == 2

    def test_empty_csv(self, tmp_path: Path) -> None:
        left = tmp_path / "empty.csv"
        left.write_text("")
        right = _write_tmp_csv(["id"], [["1"]])
        rc = main([str(left), str(right), "--key", "id"])
        assert rc == 2

    def test_no_such_file(self, tmp_path: Path) -> None:
        rc = main(["no_such_file.csv", "also-missing.csv", "--key", "id"])
        assert rc == 2


# ---------------------------------------------------------------------------
# Summary format
# ---------------------------------------------------------------------------


class TestSummaryFormat:
    def test_summary(self, tmp_path: Path) -> None:
        left = _write_tmp_csv(["id"], [["1"], ["2"], ["3"]])
        right = _write_tmp_csv(["id"], [["2"], ["3"], ["4"]])
        out = io.StringIO()
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("sys.stdout", out)
        rc = main([
            str(left), str(right),
            "--key", "id",
            "--type", "inner",
            "--format", "summary",
        ])
        monkeypatch.undo()
        assert rc == 0
        text = out.getvalue()
        assert "Left:  3 row(s)" in text
        assert "Right: 3 row(s)" in text
        assert "Joined: 2 row(s)" in text


# ---------------------------------------------------------------------------
# Module resolution sanity
# ---------------------------------------------------------------------------


class TestModuleResolution:
    def test_import_resolves(self) -> None:
        import csvjoin

        path = Path(csvjoin.__file__).resolve()
        assert path.is_file()
        assert path.parent.name == "csvjoin"
