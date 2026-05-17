# ResearchRadar

**Turn any research topic into a live literature radar.**

ResearchRadar is an open-source literature intelligence platform for creating
customizable, signal-weighted dashboards of scientific papers. Users define a
topic, choose literature sources, configure priority signals, and generate
ranked dashboards that help track emerging research across biomedical science
and beyond.

## Why ResearchRadar?

Researchers are overwhelmed by new papers. Standard alerts return long lists of
results, but they rarely explain which papers matter most or why.

ResearchRadar helps users:

- track new papers across topics
- prioritize papers using transparent scoring
- create reusable radar configurations
- monitor emerging research trends
- export literature tables for grants, reviews, and journal clubs
- share or clone dashboards

## How It Works

```text
Topic
  |
  v
Search sources
  |
  v
Extract metadata and abstracts
  |
  v
Apply signal profile
  |
  v
Calculate Research Relevance Score
  |
  v
Generate dashboard and exports
```

## Core Concepts

### Radar

A **radar** is a saved literature monitor for a research topic.

Examples:

- Cancer Evolution Radar
- AI Drug Discovery Radar
- Urban Microbiome Radar
- Single-Cell Immunology Radar

### Signal Profile

A **signal profile** tells ResearchRadar what to prioritize.

Example signal categories:

- methods
- clinical relevance
- datasets
- mechanisms
- biomarkers
- translational potential
- surveillance relevance
- therapeutic relevance
- open-source tools
- review articles

### Research Relevance Score

The **Research Relevance Score** ranks papers using a transparent weighted
model.

```text
Research Relevance Score =
topic relevance
+ recency
+ priority term matches
+ method signals
+ source metadata
+ optional user feedback
```

Each paper card explains its score with the matched topic, priority terms,
method signals, recency, source, and score components.

## Product Workflow

ResearchRadar is designed as a radar builder:

```text
Create Radar -> Enter Topic -> Choose Template -> Adjust Signals -> Generate Dashboard -> Export
```

Users can:

1. Create a radar from a topic.
2. Select sources.
3. Define priority terms.
4. Set scoring weights.
5. Generate a live dashboard.
6. Save, clone, export, or publish it.

The fastest publishable version is CLI + configs + static dashboard + examples
+ validation. User accounts, paid plans, team collaboration, and LLM summaries
can come later.

## Live Dashboard

https://aglucaci.github.io/litscan/

[![ResearchRadar](https://github.com/aglucaci/litscan/actions/workflows/litscan-radar-monthly.yml/badge.svg)](https://github.com/aglucaci/litscan/actions/workflows/litscan-radar-monthly.yml)

## Site Map

The static site now supports the MVP product and paper narrative:

- `/` - home page and live generated dashboard
- `/create/` - guided radar builder
- `/radar/cancer-evolution/` - example radar dashboard page
- `/templates/` - reusable starter radars
- `/explore/` - public radar gallery with clone actions
- `/examples/` - finished dashboards and links to configs
- `/methodology/` - Research Relevance Score explanation
- `/docs/` - usage and reproducibility documentation
- `/export/` - Research Pack export formats
- `/about/` - project purpose, audience, and open-source framing

## Quick Start

Current prototype:

```bash
pip install requests
python scripts/daily_pubmed_watch_v2.py --days 1 --max 12
```

Output:

```text
docs/index.html
docs/latest.json
docs/latest.md
```

Run tests:

```bash
python -m unittest tests.test_scoring
```

Planned package workflow:

```bash
git clone https://github.com/your-org/researchradar
cd researchradar
pip install -e .
researchradar init ai_protein_design
researchradar build radars/ai_protein_design.yml
researchradar serve results/ai_protein_design/
researchradar export results/ai_protein_design/ --format csv
researchradar export results/ai_protein_design/ --format bibtex
```

## Create Your Own Radar

### Step 1: Choose a Topic

Example:

```text
AI for protein design
```

### Step 2: Start from a Template

Starter radar configurations live in [`examples/`](examples/).

Recommended first templates:

- Cancer Evolution Radar
- Viral Evolution Radar
- Metagenomics Radar
- Urban Microbiome Radar
- AI Drug Discovery Radar
- Protein Design Radar
- Wastewater Surveillance Radar
- Single-Cell Genomics Radar

### Step 3: Edit Your Query Set

```yaml
radar_name: AI Protein Design Radar

sources:
  - pubmed
  - biorxiv
  - medrxiv

queries:
  - "protein design"
  - "protein engineering"
  - "generative model"
  - "diffusion model"
  - "protein language model"
```

### Step 4: Define Your Signal Profile

```yaml
signal_profile:
  methods:
    description: "Computational or experimental methods"
    terms:
      - diffusion model
      - protein language model
      - inverse folding
      - generative model
    weight: 2.0

  validation:
    description: "Experimental validation or benchmark evidence"
    terms:
      - wet-lab validation
      - binding assay
      - functional assay
      - benchmark
    weight: 2.5

  applications:
    description: "Applied protein engineering outcomes"
    terms:
      - enzyme design
      - antibody design
      - therapeutic protein
      - stability
    weight: 1.5
```

### Step 5: Build, View, and Publish

```bash
researchradar build radars/ai_protein_design.yml
researchradar serve results/ai_protein_design/
researchradar publish results/ai_protein_design/
```

## Example Radar Configuration

```yaml
radar_name: Cancer Evolution Radar

description: >
  Tracks papers related to cancer evolution, clonal dynamics,
  therapy resistance, tumor phylogenetics, and single-cell methods.

sources:
  - pubmed
  - biorxiv
  - medrxiv

queries:
  - "cancer evolution"
  - "clonal evolution"
  - "tumor phylogeny"
  - "therapy resistance"
  - "subclonal architecture"

filters:
  date_range: "last_90_days"
  language: "english"

signal_profile:
  biological_process:
    terms:
      - clonal selection
      - subclonal expansion
      - tumor evolution
      - lineage tracing
    weight: 2.0

  methods:
    terms:
      - single-cell sequencing
      - phylogenetic reconstruction
      - mutational signatures
      - spatial transcriptomics
    weight: 1.5

  clinical_relevance:
    terms:
      - relapse
      - minimal residual disease
      - treatment resistance
      - metastasis
    weight: 2.5

scoring:
  topic_relevance_weight: 0.35
  recency_weight: 0.20
  signal_weight: 0.35
  source_weight: 0.10

outputs:
  - dashboard
  - csv
  - bibtex
  - markdown
```

## Dashboard Features

Each dashboard includes:

- ranked papers
- Research Relevance Score
- score explanations
- matched priority terms
- source filters
- date filters
- emerging trend summaries
- saved papers
- export tools

Example paper card:

```text
Title: Clonal dynamics during therapy resistance in lung cancer

Research Relevance Score: 91

Why ranked highly:
- matched topic: therapy resistance
- matched priority signal: clonal selection
- matched method: single-cell sequencing
- matched clinical term: relapse
- recent publication: 14 days old
```

## Clone an Existing Radar

Users can clone a radar and modify it.

```bash
researchradar clone examples/cancer_evolution.yml my_leukemia_radar.yml
```

Then edit:

```yaml
radar_name: Leukemia Evolution Radar

queries:
  - "acute myeloid leukemia"
  - "clonal hematopoiesis"
  - "therapy resistance"
  - "relapse"
```

Build:

```bash
researchradar build my_leukemia_radar.yml
```

## User Levels

### Level 1: Web User

For non-technical users:

```text
Enter topic -> choose template -> adjust sliders -> generate dashboard
```

### Level 2: Config User

For scientists who want reproducibility:

```bash
researchradar build my_topic.yml
```

This is ideal for labs, papers, and GitHub workflows.

### Level 3: Developer User

For institutions and advanced users:

- add new source adapters
- add new scoring modules
- deploy a private instance
- connect internal databases
- add institutional templates
- run scheduled GitHub Actions

## Repository Structure

```text
.
|-- examples/
|   |-- cancer_evolution.yml
|   |-- viral_evolution.yml
|   |-- metagenomics.yml
|   |-- urban_microbiome.yml
|   |-- ai_drug_discovery.yml
|   |-- protein_design.yml
|   |-- wastewater_surveillance.yml
|   `-- single_cell_genomics.yml
|-- scripts/
|   `-- daily_pubmed_watch_v2.py
|-- logo/
|   `-- ResearchRadar_logo.png
|-- docs/
|   `-- index.html
|-- tests/
|   `-- test_scoring.py
|-- manuscript/
|   `-- researchradar_manuscript.md
|-- MANUSCRIPT_PLAN.md
`-- .github/workflows/
    `-- litscan-radar.yml
```

## Automation

ResearchRadar runs via GitHub Actions:

- daily radar update
- weekly deep scan
- automatic commit only when output changes
- concurrency-safe
- dependency-cached for speed

Workflow:

```text
.github/workflows/litscan-radar.yml
```

## Validation Plan

For the paper, the key missing piece is validation.

Minimum evaluation:

- use cancer evolution, viral evolution, and metagenomics case studies
- retrieve 100-300 papers per case study
- manually label relevance
- compare ResearchRadar ranking against baselines
- report Precision@10, Precision@25, nDCG@10, and Recall@50

Baselines:

- date-only ranking
- keyword-count ranking
- PubMed relevance ranking
- ResearchRadar full model

Modest claim:

> ResearchRadar improves prioritization of expert-relevant papers compared with
> date-only and keyword-count baselines.

ResearchRadar is not a replacement for systematic review. It is a surveillance
and prioritization layer.

## Paper Framing

Working title:

**ResearchRadar: customizable signal-weighted dashboards for biomedical
literature monitoring**

Core novelty statement:

> ResearchRadar introduces a configurable signal-weighted framework for
> scientific literature surveillance, allowing users to define not only which
> topics to search, but which types of evidence, methods, applications, and
> emerging research signals should influence paper prioritization.

## Roadmap

- PubMed search backend
- YAML radar config
- scoring model
- ranked CSV output
- static dashboard
- example radars
- BibTeX/RIS export
- GitHub Pages publishing
- web interface
- saved radars and user accounts
- full-text support
- LLM-assisted structured summaries
- user feedback learning
- team/shared radars
- citation graph integration

## License

MIT License
