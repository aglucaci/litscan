# Starter Radars

These starter radar configurations show how ResearchRadar should feel as a
configurable research intelligence system. Each radar defines a topic, sources,
query set, signal profile, scoring weights, and export outputs.

The current prototype may not parse every field yet. Treat these files as the
product contract for the publishable CLI and web workflow.

## Included Templates

| Template | File |
| --- | --- |
| Cancer Evolution Radar | `cancer_evolution.yml` |
| Viral Evolution Radar | `viral_evolution.yml` |
| Metagenomics Radar | `metagenomics.yml` |
| Urban Microbiome Radar | `urban_microbiome.yml` |
| AI Drug Discovery Radar | `ai_drug_discovery.yml` |
| Protein Design Radar | `protein_design.yml` |
| Wastewater Surveillance Radar | `wastewater_surveillance.yml` |
| Single-Cell Genomics Radar | `single_cell_genomics.yml` |

## Planned Commands

```bash
researchradar build examples/cancer_evolution.yml
researchradar clone examples/cancer_evolution.yml my_leukemia_radar.yml
researchradar export results/cancer_evolution/ --format csv
researchradar export results/cancer_evolution/ --format bibtex
```
