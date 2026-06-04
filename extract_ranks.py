#!/usr/bin/env python3
"""
Stream the CZI software-mentions *disambiguated* TSV and aggregate counts per
software into several curation-label buckets, in a single pass.

Convention over configuration:
  - input is read from a fixed path (see INPUT below)
  - four output tables are always written (see OUTPUTS below)

Software-name logic mirrors the notebook:
  - use `mapped_to_software`
  - if that is 'not_disambiguated' (or missing/empty), fall back to raw `software`

Why csv and not awk: the `text` column holds free text with quoted tabs/newlines.
csv.reader handles quoting and multi-line fields; an awk line pass would corrupt them.
"""

import csv
import gzip
import sys
from pathlib import Path
from collections import defaultdict

# --- Convention -------------------------------------------------------------
INPUT = Path("data/disambiguated/disambiguated/comm_disambiguated.tsv.gz")

OUTPUTS = {
    "exclude_not_software": Path("cz_aggregates_exclude_not_software.tsv"),
    "only_software": Path("cz_aggregates_only_software.tsv"),
    "unclear": Path("cz_aggregate_unclear.tsv"),
    "not_curated": Path("cz_aggregate_not_curated.tsv"),
}
# ----------------------------------------------------------------------------


def open_maybe_gz(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", newline="")
    return open(path, "rt", newline="")


def write_table(path: Path, counts: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as out_f:
        out_f.write("software\tcount\n")
        for software, count in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            out_f.write(f"{software}\t{count}\n")


def main():
    if not INPUT.exists():
        sys.exit(f"Error: input file '{INPUT}' not found")

    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

    # One counter per bucket
    buckets = {name: defaultdict(int) for name in OUTPUTS}
    label_seen = defaultdict(int)  # distribution of raw curation_label values

    print(f"Reading from: {INPUT}", file=sys.stderr)

    with open_maybe_gz(INPUT) as f:
        reader = csv.reader(f, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration:
            sys.exit("Error: empty file")

        idx = {name: i for i, name in enumerate(header)}
        for required in ("software", "pmid"):
            if required not in idx:
                sys.exit(f"column '{required}' not found in header: {header}")

        i_sw = idx["software"]
        i_pm = idx["pmid"]
        i_mp = idx.get("mapped_to_software")  # absent in some exports
        i_cl = idx.get("curation_label")
        need = max(x for x in (i_sw, i_pm, i_mp, i_cl) if x is not None)

        n = skipped_empty = 0

        for row in reader:
            n += 1
            if n % 1_000_000 == 0:
                print(f"  ...{n:,} rows read", file=sys.stderr)

            if len(row) <= need:  # short/malformed row
                continue

            label = row[i_cl] if i_cl is not None else ""
            label_seen[label] += 1

            # Software name (prefer disambiguated mapping, fall back to raw)
            m = row[i_mp] if i_mp is not None else row[i_sw]
            if m in ("not_disambiguated", ""):
                m = row[i_sw]

            pmid = row[i_pm]
            if not m or not pmid:
                skipped_empty += 1
                continue

            # --- Bucketing ---
            if label == "software":
                buckets["only_software"][m] += 1
                buckets["exclude_not_software"][m] += 1
            elif label == "unclear":
                buckets["unclear"][m] += 1
                buckets["exclude_not_software"][m] += 1
            elif label == "not_curated":
                buckets["not_curated"][m] += 1
                buckets["exclude_not_software"][m] += 1
            elif label == "not_software":
                pass  # excluded everywhere
            else:
                # unexpected label: keep it out of the curated buckets but
                # still count it toward exclude_not_software
                buckets["exclude_not_software"][m] += 1

    # --- Report -------------------------------------------------------------
    print(f"\nProcessing complete:", file=sys.stderr)
    print(f"  Total rows read: {n:,}", file=sys.stderr)
    print(f"  Skipped (empty software/pmid): {skipped_empty:,}", file=sys.stderr)
    print(
        f"\n  curation_label distribution (verify these match assumptions):",
        file=sys.stderr,
    )
    for label, c in sorted(label_seen.items(), key=lambda x: -x[1]):
        shown = repr(label) if label != "" else "'' (empty / not curated)"
        print(f"    {shown}: {c:,}", file=sys.stderr)

    # --- Write all tables ---------------------------------------------------
    print("", file=sys.stderr)
    for name, path in OUTPUTS.items():
        write_table(path, buckets[name])
        print(
            f"  Wrote {path}  ({len(buckets[name]):,} unique software)", file=sys.stderr
        )


if __name__ == "__main__":
    main()
