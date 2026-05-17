# ResearchRadar: customizable signal-weighted dashboards for biomedical literature monitoring

**Article type:** Bioinformatics Application Note or BMC Bioinformatics Software Article

**Running title:** Signal-weighted literature monitoring with ResearchRadar

**Authors:** TODO

**Affiliations:** TODO

**Corresponding author:** TODO

## Abstract

**Motivation:** Biomedical researchers face rapid growth of publications across PubMed, preprint servers, and specialized scientific domains. Standard keyword alerts and database-specific searches help retrieve new records, but they often return noisy chronological lists, provide limited personalization, and rarely explain why a paper should be prioritized for expert review. This problem is especially acute in interdisciplinary fields where relevant signals are distributed across disease areas, methods, organisms, and publication venues.

**Results:** We developed ResearchRadar, a configurable literature-monitoring system that converts user-defined research topics into live, scored dashboards. ResearchRadar retrieves scholarly records from configurable sources, applies transparent signal-weighted scoring, ranks papers by recency and scientific relevance, and generates interactive dashboards for ongoing literature surveillance. Users can define research topics, select sources, specify priority terms, adjust scoring weights, inspect ranking explanations, and export results in reusable formats.

**Validation:** We designed ResearchRadar for evaluation across biomedical case studies in cancer evolution, viral evolution, and metagenomics. The planned validation compares signal-weighted ranking against date-only, keyword-count, and database relevance baselines using expert-labeled papers and information retrieval metrics including Precision@K and nDCG@K. TODO: replace this sentence with measured validation results after expert labeling and benchmarking.

**Availability:** ResearchRadar is available as an open-source software project and static dashboard workflow. TODO: insert repository URL, documentation URL, version, license, and archived release DOI.

## 1. Introduction

Biomedical literature is expanding rapidly, making it increasingly difficult for researchers to track relevant developments across fields. New findings appear across journals, preprint servers, conference proceedings, and discipline-specific databases. Researchers who work in interdisciplinary areas often need to monitor publications that use different terminology for related concepts, such as clonal evolution in cancer, immune escape in virology, strain tracking in metagenomics, or foundation models in computational biology.

Existing tools such as PubMed alerts, Google Scholar alerts, saved database searches, systematic review platforms, and biomedical text-mining systems provide important support for literature discovery. However, many alerting workflows remain keyword-based, chronological, and weakly personalized. They often do not distinguish topical relevance from methodological novelty, do not expose field-specific evidence signals, and do not provide transparent explanations for why a particular paper should be read first.

Researchers need a lightweight system that converts a topic into a continuously updated literature radar: a ranked, inspectable, and reproducible dashboard that reflects the user's scientific priorities. Such a system should allow users to define not only what to search for, but also what kinds of evidence, methods, organisms, disease contexts, or emerging signals should influence ranking.

We present ResearchRadar, an open-source literature intelligence platform that enables users to define scientific topics, configure query sets and signal profiles, and generate live dashboards of newly published papers. Unlike conventional literature alerts, ResearchRadar scores papers using transparent, user-configurable features including recency, topic relevance, matched priority terms, source metadata, and topic-specific terminology.

ResearchRadar is intended as a surveillance and prioritization layer between simple keyword alerts and formal systematic review workflows. It does not replace expert reading or evidence synthesis. Instead, it helps researchers decide which papers to inspect first, why those papers were prioritized, and how the ranking rules can be modified for a specific lab, project, grant, or review question. In this article, we describe the system design, scoring model, dashboard interface, and validation plan for ResearchRadar across biomedical use cases including cancer evolution, viral evolution, and metagenomics.

## 2. System Overview

ResearchRadar converts a user-defined topic or radar configuration into a ranked literature dashboard. The workflow has six stages:

```text
User topic or radar config
        |
        v
Source queries
PubMed / bioRxiv / medRxiv / CrossRef / arXiv
        |
        v
Metadata and abstract retrieval
        |
        v
Text processing and feature extraction
        |
        v
Signal-weighted scoring
        |
        v
Ranking, filtering, dashboard, exports, alerts
```

ResearchRadar has four main components:

1. Radar configuration
2. Literature retrieval
3. Signal-weighted scoring
4. Dashboard generation and export

The central abstraction is a radar. A radar specifies a research topic, one or more literature sources, search queries, signal categories, scoring weights, and output settings. A user can create a radar from the web interface, by editing a human-readable configuration file, or by cloning and modifying an existing public radar.

## 3. Implementation

### 3.1 Radar Configuration

Each radar can be defined through a web interface or a human-readable configuration file. Configurations allow users to create topic-specific literature monitors without changing source code.

```yaml
radar_name: Cancer Evolution Radar

sources:
  - pubmed
  - biorxiv
  - medrxiv

queries:
  - "cancer evolution"
  - "clonal evolution"
  - "therapy resistance"
  - "tumor phylogeny"

signals:
  selection:
    terms:
      - "positive selection"
      - "clonal selection"
      - "subclonal expansion"
    weight: 2.0

  methods:
    terms:
      - "single-cell sequencing"
      - "phylogenetics"
      - "lineage tracing"
    weight: 1.5

  clinical_relevance:
    terms:
      - "therapy resistance"
      - "relapse"
      - "minimal residual disease"
    weight: 2.5
```

This design supports both no-code and reproducible workflows. No-code users can enter a topic, select sources, tune signal categories, and publish a dashboard. Power users can edit configuration files directly and rebuild dashboards from version-controlled settings.

### 3.2 Literature Sources

The initial implementation focuses on biomedical literature sources, while the architecture permits additional scholarly sources through modular source adapters. The biomedical-first version supports or is designed to support:

| Source | Role |
| --- | --- |
| PubMed | Peer-reviewed biomedical literature |
| bioRxiv | Biology preprints |
| medRxiv | Medical and clinical preprints |
| CrossRef | DOI and publisher metadata |
| Semantic Scholar | Citation and semantic metadata, where available |
| arXiv | Computational and quantitative research domains |

For each source, ResearchRadar uses a source adapter that normalizes records into a shared schema. This allows papers from multiple sources to be ranked, filtered, deduplicated, and exported together.

### 3.3 Metadata Fields

ResearchRadar stores metadata fields used for topic matching, scoring, display, filtering, and export.

| Field | Use |
| --- | --- |
| Title | Topic matching and dashboard display |
| Abstract | Signal extraction and relevance scoring |
| Authors | Author display and network summaries |
| Journal or source | Filtering and source weighting |
| Publication date | Recency scoring |
| DOI, PMID, or preprint identifier | Linking, deduplication, and export |
| Publication type | Article, review, preprint, editorial, or other category |
| Keywords or MeSH terms | Improved scoring when available |

### 3.4 Text Processing

The first version emphasizes transparent and inspectable text processing. For each record, ResearchRadar applies normalization and matching steps that may include:

- lowercasing title, abstract, and keyword text
- exact phrase matching for topic and priority terms
- synonym expansion from user-defined term lists
- optional stemming or lemmatization
- extraction of matched priority terms by category
- duplicate removal across sources using DOI, PMID, title similarity, and source identifiers

This approach prioritizes interpretability. Each matched term can be shown in the dashboard, allowing users to audit why a paper received a high score. Optional embedding-based similarity can be added as an additional feature, but the core scoring model does not depend on an opaque language model.

### 3.5 Signal-Weighted Scoring Model

The Research Relevance Score combines topic relevance, recency, matched priority terms, source or category modifiers, and optional user feedback. For paper i, the general model is:

```text
S_i = alpha * T_i + beta * R_i + gamma * M_i + delta * C_i + epsilon * U_i
```

where:

| Symbol | Meaning |
| --- | --- |
| T_i | Topic relevance |
| R_i | Recency score |
| M_i | Matched signal score |
| C_i | Cross-domain, source, or category relevance |
| U_i | Optional user feedback or saved-paper relevance |
| alpha ... epsilon | User-defined feature weights |

In practical terms:

```text
Research Relevance Score =
topic relevance
+ recency weight
+ signal term score
+ source/category modifier
+ optional user feedback adjustment
```

The matched signal score is calculated from the user-defined signal profile. If a paper matches priority terms in a category such as `clinical_relevance`, `methods`, or `surveillance`, that category contributes according to its assigned weight. A paper can receive credit from multiple categories, which allows ResearchRadar to prioritize cross-domain papers such as a metagenomic surveillance study using long-read sequencing or a cancer evolution paper combining single-cell lineage tracing with therapy resistance.

The scoring model is intentionally transparent and configurable. Each paper includes an explanation showing which terms and features contributed to its ranking. This makes the system auditable and distinguishes ResearchRadar from black-box recommendation systems.

### 3.6 Dashboard Generation and Export

ResearchRadar generates static and interactive outputs suitable for individual researchers, labs, and public research resources. Supported or planned outputs include:

- interactive web dashboard
- static HTML export
- CSV
- JSON
- BibTeX
- RIS
- Markdown summary
- GitHub Pages deployment
- scheduled update workflows

The dashboard presents ranked papers, matched priority terms, scoring explanations, trend panels, source filters, and export controls. Static export support allows a radar to be published as a versioned research artifact and shared through low-cost infrastructure such as GitHub Pages.

### 3.7 Software Architecture

The software is organized around modular components.

| Module | Function |
| --- | --- |
| `sources/` | API adapters for PubMed, preprints, CrossRef, and other databases |
| `scoring/` | Topic relevance, signal matching, recency scoring, and ranking |
| `dashboard/` | HTML and dashboard generation |
| `config/` | Radar templates and user-defined radar files |
| `exports/` | CSV, JSON, BibTeX, RIS, and Markdown export |
| `cli/` | Command-line interface |
| `web/` | Optional user interface for radar creation and tuning |

The current repository may implement these modules as scripts and templates during early development. The architecture table describes the intended package organization for a publication-ready release.

## 4. User Interface

### 4.1 Create a Radar

ResearchRadar is designed as a radar builder rather than a static dashboard. The core user workflow is:

```text
Enter topic
-> choose sources
-> define priority terms
-> set weights
-> build dashboard
-> save, clone, export, or publish
```

A user can begin with a topic such as "cancer evolution and therapy resistance" or "AI for protein design." ResearchRadar then generates a starter radar containing suggested queries, sources, signal categories, and weights. Users can accept the defaults, adjust weights with sliders, add custom signals, or switch to an advanced configuration view.

### 4.2 Paper Cards

Each paper card is designed to make prioritization transparent. Cards include:

- title
- authors
- date
- source
- abstract
- Research Relevance Score
- matched priority terms
- ranking explanation
- save and hide controls
- citation export
- links to similar papers

Example card explanation:

```text
Research Relevance Score: 87

Why this paper was ranked highly:
- matched topic: cancer evolution
- matched priority signal: therapy resistance
- matched method: single-cell sequencing
- recent publication: 12 days old
```

These explanations allow users to audit scores, tune weights, and decide whether the radar is emphasizing the right kinds of evidence.

### 4.3 Radar Dashboard

The dashboard contains panels for ranked literature monitoring and lightweight scientific intelligence.

| Panel | Purpose |
| --- | --- |
| Top papers | Ranked literature feed |
| Emerging terms | Detection of accelerating topics |
| Source distribution | Papers by source or journal |
| Signal categories | Papers grouped by scoring category |
| Timeline | Papers over time |
| Saved papers | User-curated reading list |
| Export | BibTeX, CSV, RIS, JSON, and Markdown |

The interface supports faceted filtering by source, date, field, method, paper type, author, journal, and signal category. This is important because literature radars can retrieve large result sets, and users need to narrow records according to multiple dimensions.

## 5. Validation

### 5.1 Evaluation Questions

The validation is designed to answer four questions:

1. Does ResearchRadar prioritize relevant papers better than keyword-only search?
2. Does signal-weighted scoring improve ranking compared with date-only ranking?
3. Are score explanations interpretable to domain experts?
4. Can the same framework generalize across biomedical subfields?

### 5.2 Case Studies

We propose three biomedical case studies for initial validation.

| Case study | Rationale |
| --- | --- |
| Cancer evolution | Strong domain vocabulary, translational relevance, and clear priority terms |
| Viral evolution | Selection, immune escape, recombination, host jumps, and surveillance |
| Metagenomics | Broad literature, methods-heavy signals, and heterogeneous terminology |

An optional fourth case study in AI for protein design can test generalization beyond the immediate evolutionary and biomedical surveillance domains.

### 5.3 Benchmark Dataset

The planned benchmark dataset contains 300 manually labeled papers:

```text
300 papers total
100 cancer evolution
100 viral evolution
100 metagenomics

Each paper labeled by expert review:
0 = not relevant
1 = somewhat relevant
2 = highly relevant
```

Expert labels should assess topical relevance, methodological novelty, biological importance, translational or surveillance relevance, and review priority. Labels should be produced using written guidelines and, where possible, more than one annotator to estimate agreement.

### 5.4 Baselines

ResearchRadar should be compared with practical baselines that reflect common literature monitoring workflows.

| Baseline | Description |
| --- | --- |
| Date-only | Newest papers first |
| Keyword count | Rank by number of query-term matches |
| PubMed relevance | Default PubMed sorting where available |
| Embedding similarity only | Optional baseline if embeddings are implemented |
| Full ResearchRadar model | Topic relevance, recency, signals, and weights |

### 5.5 Metrics

Information retrieval metrics will quantify ranking quality.

| Metric | Meaning |
| --- | --- |
| Precision@10 | Fraction of top 10 papers judged relevant |
| Precision@25 | Fraction of top 25 papers judged relevant |
| nDCG@10 | Ranking quality with graded relevance |
| Recall@K | Fraction of relevant papers appearing in top K |
| MRR | Rank position of the first highly relevant paper |

The minimal publishable evaluation should show whether ResearchRadar improves Precision@25 and nDCG@10 relative to date-only and keyword-count baselines across all three case studies.

### 5.6 Ablation Analysis

Ablation analysis will assess which components contribute to performance.

| Model | Removed component |
| --- | --- |
| Full ResearchRadar | None |
| No recency | Removes date weighting |
| No signal profile | Removes priority terms and signal weights |
| No source weighting | Removes source or category modifier |
| No custom weights | Uses equal weights only |

This analysis is important because the central claim of ResearchRadar is that configurable signal weighting improves literature prioritization.

### 5.7 Interpretability Evaluation

Because ResearchRadar emphasizes transparent ranking, validation should include an interpretability component. Domain experts can rate whether card-level explanations correctly identify why a paper is relevant and whether the matched priority terms help them decide what to read. A simple evaluation can ask experts to score explanations on clarity, correctness, and usefulness using a Likert scale.

## 6. Results

### 6.1 ResearchRadar Generates Topic-Specific Dashboards

ResearchRadar generates dashboards from user-defined radar configurations. In the current prototype, a radar can retrieve records from PubMed, score papers using topic-specific signal profiles, and publish a static dashboard with ranked paper cards, score explanations, and reusable data outputs.

TODO: Insert screenshots and quantitative summary of generated dashboards for cancer evolution, viral evolution, and metagenomics.

### 6.2 Signal-Weighted Scoring Improves Prioritization

TODO: Insert benchmark results after expert labeling. The expected reporting format is:

> Across three biomedical case studies, signal-weighted scoring increased the fraction of expert-prioritized papers in the top-ranked results compared with date-only and keyword-count ranking.

Performance table placeholder:

| Method | Precision@10 | Precision@25 | nDCG@10 |
| --- | ---: | ---: | ---: |
| Date-only | TBD | TBD | TBD |
| Keyword count | TBD | TBD | TBD |
| PubMed relevance | TBD | TBD | TBD |
| ResearchRadar | TBD | TBD | TBD |

### 6.3 Score Explanations Improve Interpretability

ResearchRadar paper cards expose matched topics, priority terms, recency contributions, and source metadata. This supports auditability and helps users understand whether the radar is prioritizing papers for the intended reasons.

TODO: Insert expert ratings or qualitative examples showing that explanations were useful for interpreting rankings.

### 6.4 Radar Configurations Are Reusable and Generalizable

Radar configurations are reusable scientific monitoring artifacts. A user can clone an existing radar and modify it for a narrower research question.

```text
Cancer Evolution Radar
-> Pediatric Cancer Evolution Radar
-> Therapy Resistance Radar
```

This clone-and-modify model supports field-specific monitoring without requiring users to rebuild search and scoring logic from scratch.

### 6.5 ResearchRadar Supports Reproducible Literature Monitoring

ResearchRadar supports reproducibility through versioned configurations, scheduled update workflows, static exports, and machine-readable outputs. A radar can be archived with its configuration, retrieved records, scores, and generated dashboard, allowing users to inspect how a literature view was constructed at a specific time.

## 7. Discussion

ResearchRadar provides a configurable framework for turning literature searches into transparent, signal-weighted dashboards. Its main contribution is not simply querying biomedical databases, but allowing users to define what kinds of scientific signals should influence prioritization. This makes ResearchRadar a radar builder for scientific literature rather than a static search result viewer.

ResearchRadar complements existing alerting, review, and text-mining tools. PubMed alerts and Google Scholar alerts are useful for simple topic monitoring, but they provide limited user-defined scoring and explanation. Systematic review tools are important for evidence synthesis, but they are often heavier than needed for continuous research surveillance. Biomedical text-mining systems can extract entities and relations at scale, but they may not provide a lightweight, configurable dashboard for field-specific monitoring. ResearchRadar is designed for the gap between these workflows: rapid prioritization, transparent ranking, and reproducible surveillance.

Potential use cases include weekly literature monitoring, grant preparation, review article discovery, lab journal clubs, biotech and scientific intelligence, emerging field tracking, and cross-domain scientific monitoring. In a lab setting, a shared radar could track a research program and maintain a curated reading list. In a public resource setting, a radar could monitor an emerging topic and publish a regularly updated dashboard.

Several limitations should be noted. Keyword and abstract-based scoring may miss subtle relevance, especially when important concepts are implied rather than stated. Abstracts are incomplete representations of full papers. Source coverage varies across fields, and preprint metadata can be noisy. Signal weights require user tuning, and expert labels used for validation may be subjective. ResearchRadar is therefore not a substitute for systematic review, formal evidence synthesis, or expert judgment.

Future work will extend ResearchRadar with full-text support, LLM-assisted structured summaries, user feedback learning, team radars, citation graph integration, author and institution trend mapping, alerting and email digests, additional source adapters, ontology-driven signal dictionaries, and field emergence detection. User feedback could allow a radar to learn from papers marked relevant or not relevant while preserving transparent scoring rules.

## 8. Conclusion

ResearchRadar enables researchers to construct customizable, transparent, and reproducible literature radars for monitoring rapidly evolving scientific fields. By combining topic-specific retrieval, signal-weighted scoring, ranking explanations, and interactive dashboards, ResearchRadar provides a practical layer between simple keyword alerts and formal systematic review workflows. Case studies in cancer evolution, viral evolution, and metagenomics provide a clear path for validating its utility for prioritizing emerging biomedical literature.

## 9. Figure Legends

**Figure 1. ResearchRadar workflow for configurable literature surveillance.** A user topic or radar configuration is converted into source queries, metadata retrieval, text processing, feature extraction, signal-weighted scoring, ranking, dashboard generation, and export.

**Figure 2. Example ResearchRadar dashboard.** The dashboard shows top-ranked papers, Research Relevance Scores, matched priority terms, ranking explanations, source filters, trend panels, and export controls.

**Figure 3. Signal-weighted scoring model.** Topic relevance, recency, priority terms, source metadata, and optional user feedback contribute to a transparent Research Relevance Score.

**Figure 4. Benchmark performance.** Precision@10, Precision@25, and nDCG@10 compare ResearchRadar against date-only, keyword-count, and database relevance baselines.

**Figure 5. Case-study comparison.** Example radars for cancer evolution, viral evolution, and metagenomics show distinct signal categories, top terms, and ranked papers.

## 10. Tables

### Table 1. Comparison with Existing Approaches

| Feature | PubMed alerts | Google Scholar alerts | Systematic review tools | ResearchRadar |
| --- | ---: | ---: | ---: | ---: |
| Topic alerts | yes | yes | yes | yes |
| Custom scoring | limited | no | variable | yes |
| Signal explanations | no | no | variable | yes |
| Dashboard | no | no | variable | yes |
| Reproducible config | no | no | variable | yes |
| Exportable radar | no | no | variable | yes |
| Cross-source monitoring | limited | yes | variable | yes |

### Table 2. Radar Configuration Examples

| Radar | Query examples | Signal categories |
| --- | --- | --- |
| Cancer evolution | clonal evolution, therapy resistance | selection, relapse, single-cell methods |
| Viral evolution | immune escape, recombination | host jump, selection, surveillance |
| Metagenomics | microbiome, virome, AMR | functional profiling, strain tracking, assembly |

### Table 3. Benchmark Dataset

| Case study | Papers retrieved | Papers labeled | Highly relevant papers |
| --- | ---: | ---: | ---: |
| Cancer evolution | 500 | 100 | TBD |
| Viral evolution | 500 | 100 | TBD |
| Metagenomics | 500 | 100 | TBD |

### Table 4. Performance Metrics

| Method | Precision@10 | Precision@25 | nDCG@10 |
| --- | ---: | ---: | ---: |
| Date-only | TBD | TBD | TBD |
| Keyword count | TBD | TBD | TBD |
| PubMed relevance | TBD | TBD | TBD |
| ResearchRadar | TBD | TBD | TBD |

## 11. Supplementary Material

Supplementary material should include:

- example radar YAML files
- scoring formula details
- source adapter documentation
- labeled validation dataset
- additional dashboard screenshots
- installation instructions
- CLI examples
- API documentation
- data schema

## 12. Availability and Implementation Details

**Project name:** ResearchRadar

**Repository:** TODO

**Documentation:** TODO

**Operating systems:** TODO

**Programming language:** TODO

**Dependencies:** TODO

**License:** TODO

**Archived release:** TODO

## 13. Data Availability

The validation dataset, radar configurations, retrieved metadata, and benchmark scripts will be released with the software repository where source licenses and database terms permit redistribution. Records that cannot be redistributed directly will be represented by stable identifiers and retrieval scripts.

## 14. Code Availability

The ResearchRadar source code, example radar configurations, dashboard templates, and export utilities will be made available in a public repository under an open-source license. TODO: insert URL and release DOI.

## 15. Funding

TODO

## 16. Acknowledgements

TODO

## 17. Competing Interests

TODO

## 18. References

TODO: Add formatted references for literature overload, PubMed/NCBI APIs, bioRxiv and medRxiv, CrossRef, Semantic Scholar, systematic review automation, PubTator, LiteRev, and relevant biomedical text-mining or dashboard systems.
