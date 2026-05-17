# ResearchRadar Manuscript Plan

## Working Title

ResearchRadar: customizable signal-weighted dashboards for biomedical literature monitoring

## Central Contribution

ResearchRadar should be presented as a reproducible radar-builder system for
scientific literature surveillance, not as a one-off PubMed dashboard. The
publishable contribution is the transparent scoring framework that combines
user-defined topics, source selection, signal profiles, recency weighting,
source metadata, and cross-domain bridge detection.

## Terminology

Use the general product vocabulary everywhere:

- Radar
- Research signal
- Signal profile
- Priority terms
- Scoring weights
- Research Relevance Score
- Emerging trends
- Topic dashboard
- Radar template
- Radar configuration

Avoid biology-specific phrases such as "evolutionary signal" except when
describing a specific evolutionary biology case study.

## Claim To Defend

ResearchRadar transforms research topics and source selections into
continuously updated, signal-weighted dashboards for tracking new papers,
emerging trends, and scientific signals across any field.

Avoid claiming that ResearchRadar discovers new scientific knowledge unless
trend detection, entity extraction, or expert-validated discovery workflows are
added.

## Methods Outline

1. Radar configuration

   Radar configurations define the search scope, source list, query set, signal
   profile, priority terms, scoring weights, filters, and output formats.

2. Literature retrieval

   ResearchRadar uses configurable source adapters to retrieve article metadata
   over configurable date windows. The current demo uses NCBI E-utilities /
   PubMed. Publication-ready versions should support PubMed first, then
   bioRxiv, medRxiv, CrossRef, Semantic Scholar, and arXiv through modular
   adapters.

3. Signal profile

   A signal profile defines what the user wants ResearchRadar to prioritize.
   Biomedical examples include methods, clinical relevance, datasets,
   mechanisms, biomarkers, translational potential, surveillance relevance,
   therapeutic relevance, open-source tools, and review articles.

4. Scoring model

   ```text
   Research Relevance Score =
       topic relevance
     + recency
     + priority term matches
     + method signals
     + source metadata
     + optional user feedback
   ```

   A cross-domain bonus can be assigned when a paper matches two or more signal
   categories.

5. Dashboard and reproducibility

   GitHub Actions runs ResearchRadar on a schedule and publishes versioned
   static outputs through GitHub Pages. The JSON artifact provides auditable
   score components for downstream validation.

## Minimum Product Version

The fastest publishable version is:

1. PubMed search backend
2. YAML radar config
3. Scoring model
4. Ranked CSV output
5. Static dashboard
6. Example radars
7. BibTeX/RIS export
8. GitHub Pages publishing
9. Documentation
10. Validation benchmark

## First Example Radars

Ship these first:

1. Cancer Evolution Radar
2. Viral Evolution Radar
3. Metagenomics Radar
4. Urban Microbiome Radar
5. AI Drug Discovery Radar
6. Protein Design Radar
7. Wastewater Surveillance Radar
8. Single-Cell Genomics Radar

## Minimal Validation

Create an expert-labeled benchmark using three biomedical case studies:

- Cancer evolution
- Viral evolution
- Metagenomics

For each case study:

- retrieve 100-300 papers
- manually label relevance
- compare ResearchRadar ranking against baselines

Labels:

- High: central to the radar topic and clearly worth expert review
- Medium: relevant but indirect or lower priority
- Low: retrieved by query but weak, noisy, or off topic

Baselines:

- Date-only ranking
- Keyword-count ranking
- PubMed relevance ranking
- ResearchRadar full model
- ResearchRadar without recency
- ResearchRadar without signal profile
- ResearchRadar without cross-domain bonus

Metrics:

- Precision@10
- Precision@25
- nDCG@10
- Recall@50
- Number needed to screen to find 10 high-relevance papers

Modest paper claim:

> ResearchRadar improves prioritization of expert-relevant papers compared with
> date-only and keyword-count baselines.

## Suggested Figures

1. Workflow: topic, sources, signal profile, scoring, ranking, publish
2. Signal profile and score components
3. Example dashboard with Research Relevance Score and ranking explanations
4. Precision@K or nDCG@K versus baselines
5. Case-study comparison for cancer evolution, viral evolution, and metagenomics

## Best Venue Fit

JOSS is the cleanest first target if documentation, installation, tests, and
example outputs are kept strong. Bioinformatics Application Note becomes more
plausible after the benchmark and ablation analysis are complete. BMC
Bioinformatics is a better fit if the validation, implementation, and case
studies are expanded.
