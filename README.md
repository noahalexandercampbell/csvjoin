# csvjoin — CSV JOIN CLI

Join two CSV files by key columns from the command line — inner, left, right, and full outer joins. Zero runtime dependencies beyond the Python standard library.

## Source

Source code: https://github.com/noahalexandercampbell/csvjoin

## About

`csvjoin` answers a common data-wrangling question: *How do I merge two CSV files on a shared key?* It supports all four standard join types, composite keys, different key column names per file, custom delimiters, and stdin input — all with no external dependencies.

It is the natural companion to `csvlens` (inspect), `csvdiff` (compare), and `csvpivot` (aggregate): `csvjoin` handles the merge step in a CSV-first data pipeline.

## Features

- **Four join types** — inner (default), left, right, and full outer
- **Composite keys** — join on one or more columns with `--key a b c`
- **Different key names** — `--key left_id right_id` when left and right use different column names
- **Custom delimiters** — `--delimiter '\t'` for TSV, pipe-delimited, etc.
- **Missing-value control** — `--missing NULL` for outer-join gaps
- **Summary mode** — `--format summary` reports row counts without CSV output
- **Stdin support** — pass `-` as a file path to read from stdin
- **Headerless mode** — `--no-header` for CSV files without headers
- **Zero runtime dependencies** — stdlib only: `csv`, `argparse`, `dataclasses`
- **Two output formats** — CSV (default) and summary

## Installation

```bash
pip install csvjoin
```

Or from source:

```bash
git clone <repo-url>
cd csvjoin
pip install -e .
```

Requires Python 3.11+.

## Usage

### Basic inner join

Join `employees.csv` and `salaries.csv` on the `id` column:

```bash
csvjoin employees.csv salaries.csv --key id
```

Output (CSV):

```
id,name,dept,score
1,Alice,Engineering,95
2,Bob,Marketing,87
```

### Left join (keep all left rows)

```bash
csvjoin employees.csv salaries.csv --key id --type left
```

Rows in `employees.csv` without a match in `salaries.csv` appear with empty fields for the right side.

### Full outer join

```bash
csvjoin employees.csv salaries.csv --key id --type full
```

All rows from both files appear; unmatched sides get empty fields.

### Composite key

Join on multiple columns:

```bash
csvjoin left.csv right.csv --key year region
```

### Different key column names

When the two files use different names for the same key:

```bash
csvjoin employees.csv departments.csv --key emp_id dept_id
```

The first name(s) refer to the left file, the second to the right.

### TSV or custom delimiter

```bash
csvjoin data.tsv other.tsv --key id --delimiter $'\t' --output-delimiter $'\t'
```

### Missing value for outer joins

```bash
csvjoin left.csv right.csv --key id --type left --missing NULL
```

### Summary instead of CSV

```bash
csvjoin left.csv right.csv --key id --format summary
```

Output:

```
Left:  100 row(s)
Right: 80 row(s)
Joined: 72 row(s)
Output columns: 5
  id, name, dept, score, grade
```

### Pipe from stdin

```bash
cat left.csv | csvjoin - right.csv --key id
```

### Write output to a file

```bash
csvjoin left.csv right.csv --key id -o merged.csv
```

## Project structure

```
csvjoin/
├── csvjoin.py          # Main module (flat single-module layout)
├── pyproject.toml      # Packaging and metadata
├── README.md           # This file
├── .gitignore
└── tests/
    └── test_csvjoin.py # pytest suite
```

## Tech Stack

- Python 3.11+ (stdlib only — no external runtime dependencies)
- `pyproject.toml` with setuptools
- `pytest` + `ruff` for development
- Flat single-module layout (`csvjoin.py`)

## Tags / keywords

`csv`, `join`, `merge`, `cli`, `data-wrangling`, `terminal`, `python`, `stdlib`, `etl`, `data-engineering`

## License

MIT
