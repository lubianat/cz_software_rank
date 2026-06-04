This is a small derived dataset from the CZ Software Mentions dataset with a 2022 cutoff (https://datadryad.org/dataset/doi:10.5061/dryad.6wwpzgn2c)

It has the aggregated counts for the curation categories `not_curated`, `unclear`, and `software` as well as and aggregate for the three together (i.e., excluding `not_software`).


Each of the files include two columns, `software`, with the normalize "software" (or related entity) name, and `count`, with the count of unique pmids for each disambiguated software in the `data/disambiguated/disambiguated/comm_disambiguated.tsv.gz` table of the original dataset.

Details on the original dataset can be found in:

* https://github.com/chanzuckerberg/software-mentions
* https://datadryad.org/dataset/doi:10.5061/dryad.6wwpzgn2c
* https://arxiv.org/abs/2209.00693
