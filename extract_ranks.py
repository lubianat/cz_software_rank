#!/usr/bin/env python3
"""
Stream the CZI software-mentions *disambiguated* TSV and aggregate UNIQUE PMID
counts per software into several curation-label buckets, in a single pass.

Counts distinct PMIDs (mirrors df.groupby('software').nunique() on pmid), so a
software mentioned several times in one paper counts once.

Convention over configuration: fixed input path, four fixed output tables.
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


def write_table(path: Path, pmid_sets: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as out_f:
        out_f.write("software\tcount\n")
        # count = number of distinct pmids
        for software, pmids in sorted(
            pmid_sets.items(), key=lambda x: (-len(x[1]), x[0])
        ):
            out_f.write(f"{software}\t{len(pmids)}\n")


def main():
    if not INPUT.exists():
        sys.exit(f"Error: input file '{INPUT}' not found")

    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

    # One pmid-set per bucket
    buckets = {name: defaultdict(set) for name in OUTPUTS}
    label_seen = defaultdict(int)

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
        i_mp = idx.get("mapped_to_software")
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

            m = row[i_mp] if i_mp is not None else row[i_sw]
            if m in ("not_disambiguated", ""):
                m = row[i_sw]

            pmid = row[i_pm]
            if not m or not pmid:
                skipped_empty += 1
                continue

            # --- Bucketing: add pmid to the right set(s) ---
            if label == "software":
                buckets["only_software"][m].add(pmid)
                buckets["exclude_not_software"][m].add(pmid)
            elif label == "unclear":
                buckets["unclear"][m].add(pmid)
                buckets["exclude_not_software"][m].add(pmid)
            elif label == "":
                buckets["not_curated"][m].add(pmid)
                buckets["exclude_not_software"][m].add(pmid)
            elif label == "not_software":
                pass  # excluded everywhere
            else:
                buckets["exclude_not_software"][m].add(pmid)

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
