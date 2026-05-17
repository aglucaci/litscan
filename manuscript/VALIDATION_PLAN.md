# ResearchRadar Validation Plan

This plan defines the minimum validation needed to support the software paper.

## Evaluation Questions

1. Does ResearchRadar prioritize expert-relevant papers better than date-only ranking?
2. Does signal-weighted ranking improve over keyword-count ranking?
3. Are score explanations interpretable to domain experts?
4. Does the same framework work across multiple biomedical subfields?

## Case Studies

Use three biomedical radars:

| Case study | Example template | Why it works |
| --- | --- | --- |
| Cancer evolution | `examples/cancer_evolution.yml` | Strong vocabulary, methods, and clinical relevance |
| Viral evolution | `examples/viral_evolution.yml` | Immune escape, recombination, host jumps, surveillance |
| Metagenomics | `examples/metagenomics.yml` | Broad literature and methods-heavy signals |

## Dataset

For each case study:

- retrieve 100-300 papers
- store title, abstract, source, date, DOI/PMID, and query metadata
- remove duplicates
- label each paper by expert review

Labels:

| Label | Meaning |
| --- | --- |
| 0 | Not relevant or noisy retrieval |
| 1 | Somewhat relevant but lower priority |
| 2 | Highly relevant and worth expert review |

Optional secondary labels:

- topical relevance
- methodological novelty
- translational relevance
- surveillance relevance
- review priority

## Baselines

| Method | Description |
| --- | --- |
| Date-only | Newest papers first |
| Keyword count | More query and priority term matches rank higher |
| PubMed relevance | PubMed default relevance ranking, where available |
| ResearchRadar | Topic relevance, recency, signal profile, and source metadata |

## Ablations

| Model | Removed component |
| --- | --- |
| Full ResearchRadar | None |
| No recency | Removes date weighting |
| No signal profile | Removes priority-term scoring |
| No source weighting | Removes source/category modifier |
| Equal weights | Removes custom scoring weights |

## Metrics

Report:

- Precision@10
- Precision@25
- nDCG@10
- Recall@50
- number needed to screen to find 10 highly relevant papers

The scaffold script `scripts/validate_ranking.py` computes the core metrics
from a CSV with `case_study`, `method`, `rank`, and `relevance` columns.

```bash
python scripts/validate_ranking.py manuscript/validation_rankings_template.csv
```

## Minimum Claim

ResearchRadar improves prioritization of expert-relevant papers compared with
date-only and keyword-count baselines.

Do not claim ResearchRadar replaces systematic review. It is a surveillance and
prioritization layer.
