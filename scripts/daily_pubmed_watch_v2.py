#!/usr/bin/env python3
"""
Daily PubMed Watch — PI-level Evolution / Viromics / Metagenomics radar

What this does
- Pulls PubMed hits for the last N days across PI-aligned THEMES (virome surveillance, urban microbiome,
  selection/codon models, phylodynamics, recombination, pipelines, atlases, ML-evo lane, etc.)
- Builds docs/latest.json, docs/latest.md, docs/index.html (static; GitHub Actions + Pages friendly)
- Ranks *within each theme* using a lightweight PI-style relevance score (not just PubDate)

Usage:
  python daily_pubmed_watch.py --days 1 --max 12
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


# =========================
# v2: Theme taxonomy
# =========================

NEGATIVE_COMMON: List[str] = [
    # Keep these conservative; PubMed "term" syntax can vary by endpoint/tools.
    # You can add more as you notice noise in your feed.
    "case report",
    "randomized",
    "psychology",
]

BOOSTERS_CORE: List[str] = [
    '"computational evolutionary biology"',
    '"molecular evolution"',
    "phylogenomics",
    "phylodynamics",
    "HyPhy",
    '"codon model"',
    '"dN/dS"',
    "BUSTED",
    "FEL",
    "MEME",
    "FUBAR",
    '"selection analysis"',
    "recombination",
    "reassortment",
    '"built environment"',
    '"urban microbiome"',
    "MetaSUB",
    "metagenomics",
    "virome",
    "viromics",
    '"viral metagenomics"',
    "biosurveillance",
    '"pathogen surveillance"',
    '"pandemic preparedness"',
]

BOOSTERS_METHODS: List[str] = [
    "benchmark*",
    "workflow",
    "pipeline",
    "Snakemake",
    "Nextflow",
    "WDL",
    "CWL",
    "HPC",
    "container*",
    "Docker",
    "Singularity",
    "Apptainer",
]

BOOSTERS_ML: List[str] = [
    '"machine learning"',
    '"deep learning"',
    "transformer",
    '"foundation model"',
    '"protein language model"',
    "ESM",
    "AlphaFold",
]

BOOSTERS_CANCER: List[str] = [
    '"cancer evolution"',
    '"tumor evolution"',
    '"somatic evolution"',
    '"clonal evolution"',
    '"clonal selection"',
    '"subclonal"',
    '"driver mutation"',
    '"mutational signature"',
    '"mutational signatures"',
    "lymphoma",
    "leukemia",
    '"immuno-oncology"',
]


@dataclass
class Theme:
    name: str
    core_queries: List[str]
    boosters: List[str] = field(default_factory=list)
    negatives: List[str] = field(default_factory=list)
    priority: float = 1.0  # used in scoring


THEMES: Dict[str, Theme] = {
    # Aim 1: evolutionary inference
    "Selection & codon models": Theme(
        name="Selection & codon models",
        core_queries=[
            '("dN/dS" OR "codon model" OR HyPhy OR FEL OR MEME OR FUBAR OR BUSTED OR "branch-site") '
            'AND (selection OR evolution OR adaptive OR constraint)',
            '("episodic selection" OR "positive selection" OR "diversifying selection") AND (virus OR pathogen)',
        ],
        boosters=BOOSTERS_CORE + BOOSTERS_METHODS,
        negatives=NEGATIVE_COMMON,
        priority=1.35,
    ),
        "Cancer evolution & somatic selection": Theme(
        name="Cancer evolution & somatic selection",
        core_queries=[
            '("cancer evolution" OR "tumor evolution" OR "somatic evolution" OR "clonal evolution") '
            'AND (genomics OR sequencing OR phylogen* OR "single-cell")',
            '(cancer OR tumor OR lymphoma OR leukemia) '
            'AND ("positive selection" OR "clonal selection" OR "driver mutation" OR "dN/dS" OR "selection inference")',
            '("mutational signature" OR "mutational signatures") AND (cancer OR tumor) '
            'AND (evolution OR selection OR phylogeny)',
        ],
        boosters=BOOSTERS_CORE + BOOSTERS_METHODS + BOOSTERS_CANCER,
        negatives=NEGATIVE_COMMON,
        priority=1.20,
    ),

"Recombination & mosaicism": Theme(
        name="Recombination & mosaicism",
        core_queries=[
            '(recombination OR "mosaic genome" OR breakpoint OR "gene conversion") AND (virus OR virome OR pathogen)',
            '(RDP OR GARD OR "recombination detection") AND (sequence OR alignment)',
        ],
        boosters=BOOSTERS_CORE,
        negatives=NEGATIVE_COMMON,
        priority=1.20,
    ),
    "Phylodynamics & transmission": Theme(
        name="Phylodynamics & transmission",
        core_queries=[
            '(phylodynamic* OR "time-resolved phylogeny" OR BEAST OR "birth-death" OR coalescent) AND (virus OR pathogen)',
            '("genomic epidemiology" OR "phylodynamic inference") AND (outbreak OR transmission)',
        ],
        boosters=BOOSTERS_CORE,
        negatives=NEGATIVE_COMMON,
        priority=1.20,
    ),
    # Aim 2: urban/wastewater surveillance (MetaSUB/UrbanScope aligned)
    "Urban / built environment virome": Theme(
        name="Urban / built environment virome",
        core_queries=[
            '(virome OR "viral metagenomics" OR viromics) AND ("built environment" OR urban OR subway OR transit OR surface)',
            '("urban microbiome" OR MetaSUB) AND (virus OR virome OR phage)',
        ],
        boosters=BOOSTERS_CORE + BOOSTERS_METHODS,
        negatives=NEGATIVE_COMMON,
        priority=1.30,
    ),
    "Wastewater / WBE viral surveillance": Theme(
        name="Wastewater / WBE viral surveillance",
        core_queries=[
            '("wastewater surveillance" OR WBE OR sewage) AND (virus OR virome OR pathogen OR SARS-CoV-2)',
            '(wastewater OR sewage) AND ("viral metagenomics" OR viromics) AND (variant OR lineage OR evolution)',
        ],
        boosters=BOOSTERS_CORE,
        negatives=NEGATIVE_COMMON,
        priority=1.25,
    ),
    "Pandemic preparedness & biosurveillance": Theme(
        name="Pandemic preparedness & biosurveillance",
        core_queries=[
            '("pandemic preparedness" OR biosurveillance OR "pathogen surveillance") AND (genomics OR sequencing)',
            '("early warning" OR "sentinel surveillance") AND (metagenomics OR sequencing)',
        ],
        boosters=BOOSTERS_CORE,
        negatives=NEGATIVE_COMMON,
        priority=1.15,
    ),
    # Aim 3: atlases + pipelines
    "Atlases, compendia, reference resources": Theme(
        name="Atlases, compendia, reference resources",
        core_queries=[
            '(atlas OR database OR compendium OR "reference catalog" OR resource) AND (virome OR microbiome OR pathogen)',
            '("large-scale" OR global) AND (virome OR microbiome) AND (metadata OR harmonization)',
        ],
        boosters=BOOSTERS_CORE,
        negatives=NEGATIVE_COMMON,
        priority=1.10,
    ),
    "Metagenomics benchmarking & pipelines": Theme(
        name="Metagenomics benchmarking & pipelines",
        core_queries=[
            "metagenomics AND (benchmark* OR pipeline OR \"best practices\" OR reproducible OR workflow)",
            "(Kraken2 OR MetaPhlAn OR Bracken OR Centrifuge OR Kaiju) AND (benchmark* OR evaluation)",
        ],
        boosters=BOOSTERS_METHODS + BOOSTERS_CORE,
        negatives=NEGATIVE_COMMON,
        priority=1.05,
    ),
    # Optional lane: ML + evolution (kept separate to control noise)
    "ML for evolution & pathogens": Theme(
        name="ML for evolution & pathogens",
        core_queries=[
            '("machine learning" OR "deep learning" OR transformer) AND (virus OR pathogen OR evolution OR phylogeny)',
            '("protein language model" OR ESM) AND (mutation OR evolution OR fitness)',
        ],
        boosters=BOOSTERS_ML + BOOSTERS_CORE,
        negatives=NEGATIVE_COMMON,
        priority=1.00,
    ),
}


def build_query(theme: Theme, booster_strength: int = 6, negative_strength: int = 6) -> str:
    """
    Build a PubMed ESearch 'term' string:
      (core1 OR core2 OR ...) AND (boosters...) NOT (negatives...)
    Keep booster/negative lists short to avoid overly long queries.
    """
    core = "(" + " OR ".join(f"({q})" for q in theme.core_queries) + ")"

    boosters = theme.boosters[:booster_strength]
    boost_block = ""
    if boosters:
        boost_block = " AND (" + " OR ".join(boosters) + ")"

    negatives = theme.negatives[:negative_strength]
    neg_block = ""
    if negatives:
        neg_block = " NOT (" + " OR ".join(negatives) + ")"

    return core + boost_block + neg_block


DEFAULT_QUERIES_V2: Dict[str, str] = {k: build_query(v) for k, v in THEMES.items()}


# =========================
# v2: research signal scoring
# =========================

@dataclass(frozen=True)
class SignalClass:
    name: str
    label: str
    weight: float
    patterns: List[str]


SIGNAL_CLASSES: List[SignalClass] = [
    SignalClass(
        name="selection",
        label="Selection",
        weight=3.0,
        patterns=[
            r"\bdN/dS\b",
            r"positive selection",
            r"purifying selection",
            r"diversifying selection",
            r"episodic selection",
            r"selective sweep",
            r"codon model",
            r"\bHyPhy\b|\bBUSTED\b|\bFEL\b|\bMEME\b|\bFUBAR\b",
        ],
    ),
    SignalClass(
        name="viral_evolution",
        label="Viral evolution",
        weight=2.6,
        patterns=[
            r"immune escape",
            r"antigenic drift",
            r"antigenic mapping",
            r"host jump|host shift|spillover",
            r"recombination|reassortment",
            r"variant|lineage replacement",
        ],
    ),
    SignalClass(
        name="metagenomics_surveillance",
        label="Metagenomics / surveillance",
        weight=2.4,
        patterns=[
            r"metagenomic surveillance",
            r"genomic surveillance",
            r"wastewater|WBE|sewage",
            r"virome|viromics|viral metagenomics",
            r"strain tracking|functional profiling|MAGs?\b|AMR\b",
            r"built environment|urban microbiome|MetaSUB",
        ],
    ),
    SignalClass(
        name="cancer_evolution",
        label="Cancer evolution",
        weight=2.4,
        patterns=[
            r"clonal evolution|clonal selection|clonal expansion",
            r"subclonal|tumou?r phylogen|tumou?r evolution",
            r"mutational signature",
            r"driver mutation",
            r"single-cell",
        ],
    ),
    SignalClass(
        name="methods",
        label="Methods",
        weight=1.7,
        patterns=[
            r"phylogenetic|phylogenomic|phylodynamic",
            r"Bayesian inference|BEAST|coalescent",
            r"benchmark|evaluation|best practices",
            r"Snakemake|Nextflow|CWL|WDL|reproducible|container|Docker|Singularity|Apptainer",
            r"machine learning|deep learning|transformer|foundation model|protein language model|ESM|AlphaFold",
        ],
    ),
    SignalClass(
        name="emerging_threat",
        label="Emerging threat",
        weight=2.2,
        patterns=[
            r"zoonosis|zoonotic|spillover",
            r"outbreak|pandemic potential|pandemic preparedness",
            r"early warning|sentinel surveillance|biosurveillance",
            r"emerging pathogen|emergence",
        ],
    ),
]

CROSS_DOMAIN_BONUS = 1.5

VENUE_BOOST: List[Tuple[str, float]] = [
    (r"molecular biology and evolution|mol\s*biol\s*evol", 1.8),
    (r"nature microbiology", 1.8),
    (r"genome biology", 1.6),
    (r"\bpnas\b", 1.4),
    (r"\belife\b", 1.2),
    (r"biorxiv|medrxiv", 1.0),
]


def _regex_score(text: str, patterns: List[Tuple[str, float]]) -> float:
    s = 0.0
    for pat, w in patterns:
        if re.search(pat, text, flags=re.I):
            s += w
    return s


def _signal_matches(text: str) -> Tuple[float, Dict[str, float], List[str]]:
    component_scores: Dict[str, float] = {}
    labels: List[str] = []
    total = 0.0
    for signal in SIGNAL_CLASSES:
        hit_count = 0
        for pat in signal.patterns:
            if re.search(pat, text, flags=re.I):
                hit_count += 1
        if hit_count:
            # Multiple hits within a class help, but with diminishing returns so one
            # verbose abstract cannot dominate the ranking.
            class_score = signal.weight * (1.0 + math.log(hit_count, 2))
            component_scores[signal.name] = round(class_score, 3)
            labels.append(signal.label)
            total += class_score
    return total, component_scores, labels


def recency_boost(published_date: Optional[dt.datetime], half_life_days: float = 120.0) -> float:
    """
    Exponential decay boost: 1.0 at age 0, 0.5 at half-life.
    """
    if not published_date:
        return 0.0
    now = dt.datetime.now(dt.timezone.utc)
    if published_date.tzinfo is None:
        published_date = published_date.replace(tzinfo=dt.timezone.utc)
    age_days = max(0.0, (now - published_date).total_seconds() / 86400.0)
    return math.exp(-math.log(2) * age_days / half_life_days)


def score_paper(
    title: str,
    abstract: str,
    theme_key: str,
    published_date: Optional[dt.datetime],
    venue: str,
) -> Dict[str, Any]:
    text = f"{title}\n{abstract}"
    theme_priority = THEMES.get(theme_key, Theme(theme_key, [])).priority
    research_signal, signal_components, signal_labels = _signal_matches(text)
    venue_score = _regex_score(venue, VENUE_BOOST)
    recency_score = 1.5 * recency_boost(published_date, half_life_days=120.0)
    cross_domain_score = CROSS_DOMAIN_BONUS if len(signal_labels) >= 2 else 0.0
    total = theme_priority + research_signal + venue_score + recency_score + cross_domain_score

    return {
        "score": round(float(total), 3),
        "components": {
            "theme_priority": round(float(theme_priority), 3),
            "research_signal": round(float(research_signal), 3),
            "venue": round(float(venue_score), 3),
            "recency": round(float(recency_score), 3),
            "cross_domain": round(float(cross_domain_score), 3),
        },
        "signal_components": signal_components,
        "signal_classes": signal_labels,
    }


# =========================
# PubMed E-utilities
# =========================

def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "daily-pubmed-watch/2.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def esearch(term: str, mindate: str, maxdate: str, retmax: int) -> List[str]:
    params = {
        "db": "pubmed",
        "term": term,
        "retmode": "xml",
        "retmax": str(retmax),
        "sort": "pub+date",
        "mindate": mindate,
        "maxdate": maxdate,
        "datetype": "pdat",
    }
    url = EUTILS + "esearch.fcgi?" + urllib.parse.urlencode(params)
    xml_bytes = http_get(url)
    root = ET.fromstring(xml_bytes)
    return [node.text for node in root.findall(".//IdList/Id") if node.text]


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_pubdate(article: ET.Element) -> Tuple[str, Optional[dt.datetime]]:
    """
    Best-effort parse to a display string and a datetime (UTC).
    PubMed XML is messy across records; we try a few common spots.
    """
    # Prefer ArticleDate (often has full Y/M/D)
    y = article.findtext(".//ArticleDate/Year")
    m = article.findtext(".//ArticleDate/Month")
    d = article.findtext(".//ArticleDate/Day")
    if y and m and d:
        try:
            dd = dt.datetime(int(y), int(m), int(d), tzinfo=dt.timezone.utc)
            return dd.date().isoformat(), dd
        except Exception:
            pass

    # Then PubDate
    y = article.findtext(".//JournalIssue/PubDate/Year") or article.findtext(".//PubDate/Year")
    m = article.findtext(".//JournalIssue/PubDate/Month") or article.findtext(".//PubDate/Month")
    d = article.findtext(".//JournalIssue/PubDate/Day") or article.findtext(".//PubDate/Day")
    if y:
        try:
            yy = int(y)
            mm = 1
            if m:
                m_clean = m.strip()
                if m_clean.isdigit():
                    mm = int(m_clean)
                else:
                    mm = _MONTHS.get(m_clean[:3].lower(), 1)
            dd_i = int(d) if (d and d.strip().isdigit()) else 1
            dd = dt.datetime(yy, mm, dd_i, tzinfo=dt.timezone.utc)
            disp = f"{yy:04d}-{mm:02d}" + (f"-{dd_i:02d}" if d else "")
            return disp, dd
        except Exception:
            pass

    # Then MedlineDate (often "2024 Jan-Feb" or "2023")
    med = (article.findtext(".//JournalIssue/PubDate/MedlineDate") or "").strip()
    if med:
        m = re.search(r"(\d{4})", med)
        if m:
            yy = int(m.group(1))
            dd = dt.datetime(yy, 1, 1, tzinfo=dt.timezone.utc)
            return str(yy), dd
        return med, None

    return "", None


def efetch_details(pmids: List[str], theme_key: str) -> List[Dict[str, Any]]:
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    url = EUTILS + "efetch.fcgi?" + urllib.parse.urlencode(params)
    xml_bytes = http_get(url)
    root = ET.fromstring(xml_bytes)

    items: List[Dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = (article.findtext(".//PMID") or "").strip()
        title = (article.findtext(".//ArticleTitle") or "").strip()

        # Abstract can have multiple AbstractText nodes (and labels)
        abs_nodes = article.findall(".//Abstract/AbstractText")
        abstract = " ".join([(n.text or "").strip() for n in abs_nodes if (n.text or "").strip()]).strip()

        journal = (article.findtext(".//Journal/Title") or "").strip()

        pubdate_str, pubdate_dt = _parse_pubdate(article)

        link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

        authors = []
        for a in article.findall(".//AuthorList/Author")[:6]:
            last = (a.findtext("LastName") or "").strip()
            fore = (a.findtext("ForeName") or "").strip()
            if last and fore:
                authors.append(f"{fore} {last}")
            elif last:
                authors.append(last)
        author_str = ", ".join(authors)

        snippet = abstract[:260] + ("…" if len(abstract) > 260 else "")

        score_result = score_paper(
            title=title or "",
            abstract=abstract or "",
            theme_key=theme_key,
            published_date=pubdate_dt,
            venue=journal or "",
        )

        items.append(
            {
                "pmid": pmid,
                "title": title,
                "authors": author_str,
                "journal": journal,
                "pubdate": pubdate_str,
                "pubdate_utc": pubdate_dt.isoformat() if pubdate_dt else "",
                "link": link,
                "abstract_snippet": snippet,
                "score": score_result["score"],
                "score_components": score_result["components"],
                "signal_components": score_result["signal_components"],
                "signal_classes": score_result["signal_classes"],
                "theme": theme_key,
            }
        )
    return items


def rank_and_trim(items: List[Dict[str, Any]], max_items: int) -> List[Dict[str, Any]]:
    # Sort by PI score desc; break ties by pubdate_utc desc (if present)
    def key(it: Dict[str, Any]) -> Tuple[float, str]:
        return (float(it.get("score", 0.0)), it.get("pubdate_utc", ""))

    items_sorted = sorted(items, key=key, reverse=True)
    return items_sorted[:max_items]


# =========================
# Outputs
# =========================

SITE_NAV = [
    ("Home", ""),
    ("Create Radar", "create/"),
    ("Explore Radars", "explore/"),
    ("Templates", "templates/"),
    ("Examples", "examples/"),
    ("Methodology", "methodology/"),
    ("Docs", "docs/"),
    ("About", "about/"),
]


def _page_css() -> str:
    return """
<style>
  :root{--fg:#1f2328;--muted:#57606a;--border:#d0d7de;--chip:#f6f8fa;--ink:#0b1220;--panel:#f6f8fb;--accent:#0f766e;--shadow:0 12px 34px rgba(31,35,40,.10)}
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:1120px;margin:28px auto;padding:0 18px;line-height:1.55;color:var(--fg);background:#fff}
  a{color:#0969da;text-decoration:none}a:hover{text-decoration:underline}
  .topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:10px 0 18px;border-bottom:1px solid var(--border);margin-bottom:30px}
  .brand{display:flex;align-items:center;gap:12px}.logo{height:40px;width:40px;border-radius:8px}.wordmark{font-weight:760;font-size:18px;color:var(--ink)}
  .appnav{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.appnav a{color:var(--muted);font-size:.92em;padding:6px 8px;border-radius:8px}.appnav a.active{color:var(--ink);background:var(--chip);border:1px solid var(--border)}
  .hero{padding:12px 0 24px;border-bottom:1px solid var(--border);margin-bottom:20px}.hero h1{margin:0;color:var(--ink);font-size:40px;letter-spacing:0}.hero p{max-width:800px;color:var(--muted);font-size:18px}
  .grid{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;margin:18px 0}.card{grid-column:span 4;border:1px solid var(--border);border-radius:8px;background:#fff;padding:14px;box-shadow:var(--shadow)}.wide{grid-column:span 6}.full{grid-column:span 12}
  .card h2,.card h3{margin:0 0 8px;color:var(--ink)}.card p{margin:0 0 10px;color:var(--muted)}.muted{color:var(--muted)}
  .btn{display:inline-block;border:1px solid var(--border);border-radius:8px;background:var(--chip);color:var(--ink);padding:8px 12px;font-weight:650;margin-right:6px}.btn.primary{background:var(--ink);border-color:var(--ink);color:#fff}
  .chip{display:inline-flex;align-items:center;gap:8px;background:var(--chip);border:1px solid var(--border);border-radius:999px;padding:4px 9px;font-size:.86em;margin:3px 4px 3px 0}.score{background:#ecfdf5;border-color:#99f6e4;color:#064e3b}
  .steps{counter-reset:step}.step{display:grid;grid-template-columns:36px 1fr;gap:10px;align-items:start;border:1px solid var(--border);border-radius:8px;padding:12px;margin:10px 0}.step:before{counter-increment:step;content:counter(step);display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:999px;background:var(--ink);color:#fff;font-weight:700}
  .panel{border:1px solid var(--border);border-radius:8px;background:var(--panel);padding:14px;margin:14px 0}.yaml,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}.yaml{white-space:pre-wrap;background:#0b1220;color:#e5eef8;border-radius:8px;padding:12px;overflow:auto}
  table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid var(--border);padding:8px;text-align:left}th{background:var(--chip);color:var(--ink)}
  @media(max-width:760px){.topbar{align-items:flex-start;flex-direction:column}.card,.wide,.full{grid-column:span 12}.hero h1{font-size:32px}}
</style>
"""


def _site_header(active: str, root_prefix: str = "../") -> str:
    nav = []
    for label, href in SITE_NAV:
        target = root_prefix + href
        cls = " class='active'" if label == active else ""
        nav.append(f"<a{cls} href='{target}'>{html.escape(label)}</a>")
    return (
        "<div class='topbar'><div class='brand'>"
        "<img src='https://raw.githubusercontent.com/aglucaci/litscan/refs/heads/main/logo/ResearchRadar_logo.png' alt='ResearchRadar Logo' class='logo'/>"
        "<div class='wordmark'>ResearchRadar</div></div>"
        f"<nav class='appnav'>{''.join(nav)}</nav></div>"
    )


def _write_site_page(outdir_docs: str, slug: str, title: str, subtitle: str, active: str, body: str) -> None:
    page_dir = os.path.join(outdir_docs, slug)
    os.makedirs(page_dir, exist_ok=True)
    page_path = os.path.join(page_dir, "index.html")
    depth = len([part for part in slug.replace("\\", "/").split("/") if part])
    root_prefix = "../" * depth
    content = (
        "<!doctype html><html><head><meta charset='utf-8'/>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
        f"<title>{html.escape(title)} - ResearchRadar</title>"
        f"{_page_css()}</head><body>"
        f"{_site_header(active, root_prefix)}"
        f"<section class='hero'><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></section>"
        f"{body}"
        "<div class='muted' style='margin:28px 0 10px'>ResearchRadar is open-source literature intelligence infrastructure. Static pages are generated with the radar dashboard.</div>"
        "</body></html>"
    )
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(content)


def _template_cards() -> str:
    templates = [
        ("Cancer Evolution", "Clonal evolution, therapy resistance, tumor phylogeny, single-cell methods.", "PubMed, bioRxiv, medRxiv", "clinical relevance, methods, clonal dynamics"),
        ("Viral Evolution", "Immune escape, recombination, host jumps, phylodynamics, surveillance.", "PubMed, bioRxiv, medRxiv", "immune escape, transmission, methods"),
        ("Metagenomics", "MAGs, strain tracking, viromes, AMR, functional profiling.", "PubMed, bioRxiv, medRxiv", "methods, surveillance, resources"),
        ("AI Drug Discovery", "Generative chemistry, docking, screening, target discovery, translation.", "PubMed, bioRxiv, arXiv", "methods, validation, translation"),
        ("Protein Design", "Protein language models, diffusion models, inverse folding, validation.", "PubMed, bioRxiv, arXiv", "methods, validation, applications"),
        ("Single-Cell Genomics", "scRNA-seq, multiome, perturb-seq, atlases, lineage tracing.", "PubMed, bioRxiv, medRxiv", "methods, resources, biological insight"),
        ("Wastewater Surveillance", "Pathogen detection, AMR, viral load, public health monitoring.", "PubMed, bioRxiv, medRxiv", "public health, pathogens, methods"),
        ("Urban Microbiome", "Built environment, transit systems, city-scale sampling, viromes.", "PubMed, bioRxiv, medRxiv", "spatial sampling, surveillance, methods"),
    ]
    cards = ["<div class='grid'>"]
    for name, desc, sources, signals in templates:
        cards.append(
            "<div class='card'>"
            f"<h3>{html.escape(name)} Radar</h3><p>{html.escape(desc)}</p>"
            f"<p><b>Sources:</b> {html.escape(sources)}</p>"
            f"<p><b>Default signals:</b> {html.escape(signals)}</p>"
            "<a class='btn primary' href='../create/'>Use template</a>"
            "</div>"
        )
    cards.append("</div>")
    return "".join(cards)


def _write_product_pages(outdir_docs: str, payload: Dict[str, Any]) -> None:
    _write_site_page(
        outdir_docs,
        "create",
        "Create Radar",
        "Build a guided literature radar from a topic, template, sources, priority terms, and scoring weights.",
        "Create Radar",
        """
<div class='steps'>
  <div class='step'><div><h3>Enter topic</h3><p>Start with a field, disease, method, organism, or research question.</p><p><span class='chip'>AI for protein design</span><span class='chip'>Cancer evolution</span><span class='chip'>Urban microbiome</span></p></div></div>
  <div class='step'><div><h3>Choose template</h3><p>Pick a starter radar so sources, priority terms, and scoring weights are useful immediately.</p></div></div>
  <div class='step'><div><h3>Select sources</h3><p>Choose PubMed first, then add bioRxiv, medRxiv, arXiv, CrossRef, Semantic Scholar, RSS feeds, or DOI lists as adapters mature.</p></div></div>
  <div class='step'><div><h3>Add priority terms</h3><p>Define what counts as a research signal: methods, datasets, validation, clinical relevance, surveillance relevance, or custom terms.</p></div></div>
  <div class='step'><div><h3>Adjust scoring weights</h3><p>Tune recency, topic relevance, priority signals, source metadata, and optional feedback.</p></div></div>
  <div class='step'><div><h3>Generate dashboard</h3><p>Publish a live dashboard with ranked papers, explanations, filters, saved papers, and exports.</p></div></div>
</div>
<div class='panel'><h2>Starter config preview</h2><div class='yaml'>radar_name: AI Protein Design Radar
sources:
  - pubmed
  - biorxiv
  - arxiv
queries:
  - "protein design"
  - "diffusion model"
  - "protein language model"
signal_profile:
  validation:
    terms:
      - wet-lab validation
      - binding assay
    weight: 2.5</div></div>
""",
    )

    _write_site_page(
        outdir_docs,
        "templates",
        "Radar Templates",
        "Reusable starting points for biomedical science, AI, public health, and general research domains.",
        "Templates",
        _template_cards(),
    )

    public_cards = """
<div class='grid'>
  <div class='card'><h3>Cancer Evolution Radar</h3><p>Tracks clonal evolution, therapy resistance, tumor phylogeny, and single-cell methods.</p><p><span class='chip'>Updated today</span><span class='chip'>184 papers</span><span class='chip'>12 emerging signals</span></p><a class='btn primary' href='../radar/cancer-evolution/'>View Radar</a><a class='btn' href='../create/'>Clone</a></div>
  <div class='card'><h3>AI Drug Discovery Radar</h3><p>Tracks generative chemistry, docking, screening, target discovery, benchmarks, and validation.</p><p><span class='chip'>Updated weekly</span><span class='chip'>96 papers</span><span class='chip'>8 emerging signals</span></p><a class='btn primary' href='../radar/cancer-evolution/'>View Radar</a><a class='btn' href='../create/'>Clone</a></div>
  <div class='card'><h3>Urban Microbiome Radar</h3><p>Tracks built environment microbiomes, wastewater, city-scale sampling, and public health surveillance.</p><p><span class='chip'>Updated weekly</span><span class='chip'>73 papers</span><span class='chip'>6 emerging signals</span></p><a class='btn primary' href='../radar/cancer-evolution/'>View Radar</a><a class='btn' href='../create/'>Clone</a></div>
</div>
"""
    _write_site_page(outdir_docs, "explore", "Explore Public Radars", "Discover featured, trending, and recently updated public radars. Clone any radar to make it your own.", "Explore Radars", public_cards)

    _write_site_page(
        outdir_docs,
        "examples",
        "Examples",
        "Finished dashboards that show what ResearchRadar can do and link back to reproducible configs.",
        "Examples",
        """
<div class='grid'>
  <div class='card wide'><h3>Cancer Evolution Radar</h3><p><b>Tracks:</b> clonal dynamics, therapy resistance, tumor phylogenetics, single-cell methods.</p><p><b>Search terms:</b> cancer evolution, clonal evolution, tumor phylogeny, therapy resistance.</p><p><b>Priority signals:</b> biological process, methods, clinical relevance.</p><a class='btn primary' href='../radar/cancer-evolution/'>Open dashboard</a><a class='btn' href='../../examples/cancer_evolution.yml'>Config file</a></div>
  <div class='card wide'><h3>Protein Design Radar</h3><p><b>Tracks:</b> diffusion models, protein language models, inverse folding, enzyme design, validation.</p><p><b>Priority signals:</b> methods, validation, applications.</p><a class='btn primary' href='../templates/'>Use template</a><a class='btn' href='../../examples/protein_design.yml'>Config file</a></div>
  <div class='card wide'><h3>Wastewater Surveillance Radar</h3><p><b>Tracks:</b> pathogen detection, AMR, viral load, public health monitoring.</p><p><b>Priority signals:</b> public health, pathogens, methods.</p><a class='btn primary' href='../templates/'>Use template</a><a class='btn' href='../../examples/wastewater_surveillance.yml'>Config file</a></div>
</div>
""",
    )

    _write_site_page(
        outdir_docs,
        "methodology",
        "Methodology",
        "How the Research Relevance Score ranks papers using transparent, user-defined signals.",
        "Methodology",
        """
<div class='panel'><p><b>ResearchRadar does not decide whether a paper is good.</b> It ranks papers according to the topic and priority signals defined by the user.</p></div>
<div class='grid'>
  <div class='card'><h3>Topic relevance</h3><p>Does the title, abstract, and metadata match the radar query set?</p></div>
  <div class='card'><h3>Recency weighting</h3><p>Recent papers can receive a boost, with decay over time.</p></div>
  <div class='card'><h3>Priority term matching</h3><p>Matched terms from the signal profile increase score according to category weights.</p></div>
  <div class='card'><h3>Source metadata</h3><p>Journal, source, publication type, DOI, PMID, and preprint metadata can influence filtering and ranking.</p></div>
  <div class='card'><h3>User-defined weights</h3><p>Users decide whether methods, clinical relevance, datasets, reviews, or recency matter most.</p></div>
  <div class='card'><h3>Limitations</h3><p>Abstract-based scoring can miss subtle relevance and is not a substitute for expert review or systematic review.</p></div>
</div>
<div class='panel'><h2>Formula</h2><div class='yaml'>Research Relevance Score =
topic relevance
+ recency
+ priority term matches
+ method signals
+ source metadata
+ optional user feedback</div></div>
""",
    )

    _write_site_page(
        outdir_docs,
        "docs",
        "Documentation",
        "Use ResearchRadar from the web workflow, YAML configs, CLI, and GitHub Pages publishing.",
        "Docs",
        """
<div class='grid'>
  <div class='card'><h3>Getting started</h3><p>Create a radar from a topic, template, sources, and priority terms.</p></div>
  <div class='card'><h3>Using templates</h3><p>Start from reusable radar configurations in the examples directory.</p></div>
  <div class='card'><h3>Editing signal profiles</h3><p>Signal profiles define priority terms and weights for research signals.</p></div>
  <div class='card'><h3>Understanding scores</h3><p>Every score should be explainable from matched terms and score components.</p></div>
  <div class='card'><h3>Exporting results</h3><p>Use CSV, JSON, BibTeX, RIS, and Markdown outputs for research workflows.</p></div>
  <div class='card'><h3>Publishing</h3><p>Static dashboards can be published through GitHub Pages or similar hosts.</p></div>
</div>
<div class='panel'><h2>Current prototype</h2><div class='yaml'>python scripts/daily_pubmed_watch_v2.py --days 14 --max 25 --docs-dir docs
python -m unittest tests.test_scoring</div></div>
""",
    )

    _write_site_page(
        outdir_docs,
        "export",
        "Research Pack Exports",
        "Turn radar results into research-ready outputs for grants, reviews, journal clubs, and reproducible monitoring.",
        "Docs",
        """
<div class='grid'>
  <div class='card'><h3>Data exports</h3><p>CSV, JSON, BibTeX, and RIS for analysis and citation managers.</p></div>
  <div class='card'><h3>Briefings</h3><p>Markdown literature summaries, weekly digests, and saved reading lists.</p></div>
  <div class='card'><h3>Review seeds</h3><p>Grant background tables, journal club lists, and systematic review seed tables.</p></div>
</div>
""",
    )

    _write_site_page(
        outdir_docs,
        "about",
        "About ResearchRadar",
        "ResearchRadar helps researchers move from passive literature alerts to active, configurable research surveillance.",
        "About",
        """
<div class='grid'>
  <div class='card wide'><h3>What it is</h3><p>A customizable literature intelligence platform for live, scored, shareable research dashboards.</p></div>
  <div class='card wide'><h3>Who it is for</h3><p>Scientists, labs, analysts, reviewers, journal clubs, and open-source research communities.</p></div>
  <div class='card wide'><h3>Open-source philosophy</h3><p>The academic version prioritizes transparent scoring, reproducible configs, public templates, and self-hostable dashboards.</p></div>
  <div class='card wide'><h3>Citation</h3><p>Use the manuscript draft and repository release DOI once available.</p></div>
</div>
""",
    )

    top_items: List[Dict[str, Any]] = []
    for section in payload.get("sections", []):
        top_items.extend(section.get("items", [])[:2])
    paper_cards = ["<div class='grid'>"]
    for item in top_items[:6]:
        title = html.escape(item.get("title") or "(no title)")
        score = int(min(99, max(0, round(float(item.get("score", 0.0) or 0.0) * 5.0))))
        meta = " | ".join(x for x in [item.get("authors", ""), item.get("journal", ""), item.get("pubdate", "")] if x)
        signals = ", ".join(item.get("signal_classes", [])[:3]) or "topic and recency"
        paper_cards.append(
            "<div class='card wide'>"
            f"<h3>{title}</h3><p>{html.escape(meta)}</p>"
            f"<p><span class='chip score'>Research Relevance Score {score}</span></p>"
            f"<p><b>Why ranked highly:</b> matched radar topic, recent publication, research signals: {html.escape(signals)}.</p>"
            "<a class='btn'>Save</a><a class='btn'>Hide</a><a class='btn'>Export</a>"
            "</div>"
        )
    paper_cards.append("</div>")
    radar_body = (
        "<div class='panel'><h2>Summary</h2><p>Cancer Evolution Radar tracks clonal evolution, therapy resistance, tumor phylogeny, and single-cell methods.</p>"
        "<p><span class='chip'>Top papers</span><span class='chip'>Emerging signals</span><span class='chip'>Topic trends</span><span class='chip'>Saved papers</span><span class='chip'>Exports</span></p></div>"
        "<div class='grid'><div class='card'><h3>Emerging signals</h3><p>therapy resistance, single-cell lineage tracing, tumor phylogeny</p></div>"
        "<div class='card'><h3>Source distribution</h3><p>PubMed-indexed papers in the current prototype.</p></div>"
        "<div class='card'><h3>Exports</h3><p>CSV, JSON, BibTeX, RIS, Markdown briefing.</p></div></div>"
        + "".join(paper_cards)
    )
    _write_site_page(outdir_docs, os.path.join("radar", "cancer-evolution"), "Cancer Evolution Radar", "A sample radar dashboard with ranked papers, explanations, filters, trends, and exports.", "Explore Radars", radar_body)


def write_outputs(outdir_docs: str, payload: Dict[str, Any]) -> None:
    # JSON
    json_path = f"{outdir_docs}/latest.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # Markdown
    md_path = f"{outdir_docs}/latest.md"
    lines: List[str] = []
    lines.append("# ResearchRadar scientific literature radar\n")
    lines.append(f"**Updated:** {payload['generated_at_local']}  ")
    lines.append(f"**Window:** last {payload['days']} day(s)  ")
    lines.append("**Ranking:** Research Relevance Score (topic priority + research signals + source metadata + recency + cross-domain bridge)\n")

    for block in payload["sections"]:
        lines.append(f"\n## {block['label']} — {block['count']} result(s)\n")
        if not block["items"]:
            lines.append("_No new items in this window._")
            continue
        for it in block["items"]:
            title = it["title"] or "(no title)"
            score = it.get("score", 0.0)
            lines.append(f"- **[{title}]({it['link']})**  ")
            meta = " · ".join([x for x in [it["authors"], it["journal"], it["pubdate"]] if x])
            if meta:
                lines.append(f"  {meta}  ")
            signals = ", ".join(it.get("signal_classes", []))
            lines.append(f"  _Research Relevance Score:_ `{score}`  ")
            if signals:
                lines.append(f"  _Signals:_ {signals}  ")
            if it["abstract_snippet"]:
                lines.append(f"  _{it['abstract_snippet']}_")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")


    # HTML page (self-contained; GitHub Pages friendly)
    html_path = f"{outdir_docs}/index.html"
    html_body: List[str] = []
    html_body.append("<!doctype html><html><head><meta charset='utf-8'/>")
    html_body.append("<meta name='viewport' content='width=device-width,initial-scale=1'/>")
    html_body.append("<link rel='icon' type='image/png' href='https://raw.githubusercontent.com/aglucaci/litscan/refs/heads/main/logo/ResearchRadar_logo.png'/>")
    html_body.append("<link rel='shortcut icon' type='image/png' href='https://raw.githubusercontent.com/aglucaci/litscan/refs/heads/main/logo/ResearchRadar_logo.png'/>")
    html_body.append("<link rel='apple-touch-icon' href='https://raw.githubusercontent.com/aglucaci/litscan/refs/heads/main/logo/ResearchRadar_logo.png'/>")
    html_body.append("<title>ResearchRadar - Live Literature Radars for Science</title>")
    html_body.append("""
<style>
  :root{
    --fg:#1f2328; --muted:#57606a; --border:#d0d7de; --card:#ffffff; --chip:#f6f8fa;
    --link:#0969da; --ink:#0b1220; --panel:#f6f8fb; --accent:#0f766e;
    --shadow:0 12px 34px rgba(31,35,40,.10);
  }
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:1180px;margin:28px auto;padding:0 18px;line-height:1.55;color:var(--fg);background:#fff}
  a{color:var(--link);text-decoration:none} a:hover{text-decoration:underline}
  .muted{color:var(--muted)}
  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}
  .chip{display:inline-flex;align-items:center;gap:8px;background:var(--chip);border:1px solid var(--border);border-radius:999px;padding:4px 10px;font-size:.85em;color:#24292f}
  .chip b{font-weight:650}
  .topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:10px 0 18px;border-bottom:1px solid var(--border);margin-bottom:30px}
  .brand{display:flex;align-items:center;gap:12px}
  .logo{height:42px;width:42px;border-radius:8px;filter:drop-shadow(0 0 10px rgba(15,118,110,.18))}
  .wordmark{font-weight:760;font-size:18px;color:var(--ink)}
  .appnav{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
  .appnav a{color:var(--muted);font-size:.92em;padding:6px 8px;border-radius:8px}
  .appnav a.active{color:var(--ink);background:var(--chip);border:1px solid var(--border)}
  .hero{padding:18px 0 24px;border-bottom:1px solid var(--border);margin-bottom:20px}
  .hero h1{margin:0;color:var(--ink);font-size:44px;line-height:1.05;letter-spacing:0}
  .hero .subtitle{margin:10px 0 18px;max-width:760px;font-size:19px;color:var(--muted)}
  .searchbox{border:1px solid var(--border);background:#fff;border-radius:10px;box-shadow:var(--shadow);display:flex;gap:10px;align-items:center;padding:10px;max-width:880px}
  .searchbox input{border:0;outline:0;flex:1;min-width:180px;font-size:16px;padding:8px;color:var(--ink)}
  .btn{border:1px solid var(--border);border-radius:8px;background:var(--chip);color:var(--ink);padding:9px 13px;font-weight:650}
  .btn.primary{background:var(--ink);color:#fff;border-color:var(--ink)}
  .btn.small{padding:5px 9px;font-size:.86em}
  .examples{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;color:var(--muted);font-size:.94em}
  .examples a{border:1px solid var(--border);border-radius:999px;padding:4px 9px;background:#fff;color:var(--fg)}
  .meta{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
  .section-title{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:28px 0 10px}
  .section-title h2{margin:0;font-size:20px;color:var(--ink)}
  .section-title p{margin:4px 0 0;color:var(--muted)}
  .grid{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;margin:18px 0 20px}
  .stat{grid-column:span 3;border:1px solid var(--border);border-radius:8px;background:var(--card);padding:12px 14px;box-shadow:var(--shadow)}
  .stat .k{font-size:.78em;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
  .stat .v{margin-top:4px;font-size:1.1em;font-weight:700}
  .stat .s{margin-top:6px;font-size:.92em;color:var(--muted)}
  .value .stat{grid-column:span 4}
  .controls{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;border:1px solid var(--border);border-radius:8px;background:var(--panel);padding:14px;margin:18px 0 22px}
  .control{grid-column:span 3;background:#fff;border:1px solid var(--border);border-radius:8px;padding:12px}
  .control.wide{grid-column:span 6}
  .control.full{grid-column:span 12}
  .control label{display:block;font-size:.78em;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:8px}
  .control input[type=text], .control textarea{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:8px;padding:9px;font-size:15px;font-family:inherit;color:var(--ink);background:#fff}
  .control textarea{min-height:68px;resize:vertical}
  .checks{display:flex;flex-wrap:wrap;gap:8px}
  .checks span{border:1px solid var(--border);border-radius:999px;background:var(--chip);padding:4px 9px;font-size:.9em}
  .templates{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;margin:12px 0 22px}
  .template{grid-column:span 4;border:1px solid var(--border);border-radius:8px;background:#fff;padding:13px;box-shadow:var(--shadow)}
  .template h3{margin:0 0 6px;font-size:16px;color:var(--ink)}
  .template p{margin:0;color:var(--muted);font-size:.94em}
  .stepper{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;margin:14px 0 22px}
  .step{grid-column:span 4;border:1px solid var(--border);border-radius:8px;background:#fff;padding:13px}
  .step b{display:inline-flex;width:24px;height:24px;align-items:center;justify-content:center;border-radius:999px;background:var(--ink);color:#fff;margin-right:8px;font-size:.86em}
  .builder-grid{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;margin:14px 0 24px}
  .builder-main{grid-column:span 8}
  .builder-side{grid-column:span 4}
  .builder-panel{border:1px solid var(--border);border-radius:8px;background:#fff;padding:14px;box-shadow:var(--shadow);margin-bottom:12px}
  .builder-panel h3{margin:0 0 10px;font-size:17px;color:var(--ink)}
  .mode-tabs{display:flex;gap:8px;margin:8px 0 10px}
  .mode-tabs span{border:1px solid var(--border);border-radius:999px;padding:4px 10px;background:var(--chip);font-size:.9em}
  .mode-tabs .active{background:var(--ink);border-color:var(--ink);color:#fff}
  .weights{display:grid;gap:10px}
  .weight-row{display:grid;grid-template-columns:minmax(160px,1fr) minmax(140px,220px) 42px;gap:10px;align-items:center;font-size:.94em}
  .bar{height:8px;border-radius:999px;background:var(--chip);border:1px solid var(--border);overflow:hidden}
  .bar span{display:block;height:100%;background:var(--accent)}
  .yaml{white-space:pre-wrap;background:#0b1220;color:#e5eef8;border-radius:8px;padding:12px;font-size:.86em;line-height:1.45;overflow:auto}
  .tabs{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
  .tabs span{border:1px solid var(--border);border-radius:999px;padding:5px 10px;background:var(--chip);font-size:.9em}
  .tabs .active{background:var(--ink);border-color:var(--ink);color:#fff}
  .insights{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;margin:12px 0 22px}
  .insight{grid-column:span 4;border:1px solid var(--border);border-radius:8px;background:#fff;padding:13px;box-shadow:var(--shadow)}
  .insight h3{margin:0 0 8px;font-size:16px;color:var(--ink)}
  .insight ul{margin:0;padding-left:18px;color:var(--muted)}
  .trend-up{color:var(--accent);font-weight:700}
  .tree{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;white-space:pre-wrap;color:var(--fg);font-size:.92em}
  .why{border:1px solid var(--border);background:var(--panel);border-radius:8px;padding:10px;margin-top:10px}
  .why b{display:block;margin-bottom:6px;color:var(--ink)}
  .why ul{margin:0;padding-left:18px;color:var(--muted)}
  .actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
  .score-pill{background:#ecfdf5;border-color:#99f6e4;color:#064e3b}
  @media (max-width: 980px){ .stat{grid-column:span 6} }
  @media (max-width: 980px){ .value .stat,.template,.control,.control.wide,.step,.builder-main,.builder-side,.insight{grid-column:span 6} }
  @media (max-width: 640px){ .hero h1{font-size:34px}.searchbox{align-items:stretch;flex-direction:column}.stat,.value .stat,.template,.control,.control.wide,.control.full,.step,.builder-main,.builder-side,.insight{grid-column:span 12}.topbar{align-items:flex-start;flex-direction:column}.weight-row{grid-template-columns:1fr} }

  .nav{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0 22px}
  .nav a{border:1px solid var(--border);background:var(--chip);border-radius:12px;padding:6px 10px;font-size:.9em}

  .block{border:1px solid var(--border);border-radius:8px;background:var(--card);padding:14px 14px 10px;margin:14px 0;box-shadow:var(--shadow)}
  .blockhead{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}
  .blocktitle{display:flex;align-items:center;gap:10px}
  .blocktitle h2{margin:0;font-size:18px}
  .count{background:var(--chip);border:1px solid var(--border);border-radius:999px;padding:3px 10px;font-size:.85em;color:#24292f}
  details{margin-top:6px}
  details summary{cursor:pointer;color:var(--muted)}
  .card{border:1px solid var(--border);border-radius:8px;padding:12px 12px;margin:10px 0;background:#fff}
  .card .t{font-weight:650}
  .card .meta{margin-top:6px;font-size:.92em;color:var(--muted)}
  .card .abs{margin-top:9px;color:var(--muted);font-size:.95em}
  .signals{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
  .score{margin-left:8px}
  .footer{margin:26px 0 10px;color:var(--muted);font-size:.95em}
</style>
""")
    html_body.append("</head><body>")

    # Top summary
    total_hits = sum(int(s.get("count", 0) or 0) for s in payload.get("sections", []))
    theme_count = len(payload.get("sections", []))
    html_body.append("<header>")
    html_body.append("<div class='topbar'>")
    html_body.append("<div class='brand'>")
    html_body.append("<img src='https://raw.githubusercontent.com/aglucaci/litscan/refs/heads/main/logo/ResearchRadar_logo.png' alt='ResearchRadar Logo' class='logo'/>")
    html_body.append("<div class='wordmark'>ResearchRadar</div>")
    html_body.append("</div>")
    html_body.append("<nav class='appnav'>")
    html_body.append("<a href='#home'>Home</a>")
    html_body.append("<a href='create/'>Create Radar</a>")
    html_body.append("<a href='explore/'>Explore Radars</a>")
    html_body.append("<a href='templates/'>Templates</a>")
    html_body.append("<a href='examples/'>Examples</a>")
    html_body.append("<a href='methodology/'>Methodology</a>")
    html_body.append("<a href='docs/'>Docs</a>")
    html_body.append("<a href='about/'>About</a>")
    html_body.append("<a href='https://github.com/aglucaci/litscan' target='_blank' rel='noopener'>GitHub</a>")
    html_body.append("</nav>")
    html_body.append("<div class='meta'>")
    html_body.append(f"<span class='chip'><b>Updated</b> {html.escape(payload['generated_at_local'])}</span>")
    html_body.append(f"<span class='chip'><b>Window</b> last {int(payload['days'])} day(s)</span>")
    html_body.append("</div>")
    html_body.append("</div>")

    html_body.append("<section class='hero' id='home'>")
    html_body.append("<h1>ResearchRadar</h1>")
    html_body.append(
        "<p class='subtitle'>Turn any research topic into a live literature radar.</p>"
    )
    html_body.append("<div class='searchbox'>")
    html_body.append("<input type='text' value='cancer evolution and therapy resistance' aria-label='What do you want to track?'/>")
    html_body.append("<button class='btn primary'>Create a Radar</button>")
    html_body.append("<a class='btn' href='#templates'>Explore Examples</a>")
    html_body.append("</div>")
    html_body.append("<p class='muted' style='max-width:820px;margin-top:12px'>Create customizable dashboards that track new papers, emerging trends, and scientific signals across PubMed, preprints, and scholarly databases.</p>")
    html_body.append("<div class='examples'><span>Examples:</span>")
    for ex in ["cancer evolution", "AI drug discovery", "wastewater surveillance", "protein design"]:
        html_body.append(f"<a href='#templates'>{html.escape(ex)}</a>")
    html_body.append("</div>")
    html_body.append("</section>")

    html_body.append("<section id='explore'>")
    html_body.append("<div class='section-title'><div><h2>How A Radar Gets Built</h2><p>No YAML required at first. ResearchRadar generates a starter radar that can be tuned visually or exported as config.</p></div></div>")
    html_body.append("<div class='stepper'>")
    for num, title, desc in [
        ("1", "Enter a topic", "Start with a field, disease, method, organism, or research question."),
        ("2", "Tune the signal", "Choose sources, search terms, signal categories, and scoring weights."),
        ("3", "Publish the radar", "Save, clone, export, and monitor a live dashboard."),
    ]:
        html_body.append(f"<div class='step'><p><b>{num}</b>{html.escape(title)}</p><p class='muted'>{html.escape(desc)}</p></div>")
    html_body.append("</div>")
    html_body.append("</section>")

    html_body.append("<section id='signals'>")
    html_body.append("<div class='section-title'><div><h2>Scientific Intelligence Workflow</h2><p>Search broadly, score what matters, and publish a monitorable radar.</p></div></div>")
    html_body.append("<div class='grid value'>")
    html_body.append("<div class='stat'><div class='k'>Search any field</div><div class='v'>Multi-source radar</div>"
                     "<div class='s'>Create a radar from PubMed, arXiv, bioRxiv, medRxiv, CrossRef, Semantic Scholar, or custom sources.</div></div>")
    html_body.append("<div class='stat'><div class='k'>Score what matters</div><div class='v'>Custom signal</div>"
                     "<div class='s'>Rank by recency, topic relevance, novelty, methods, clinical relevance, translational value, or custom terms.</div></div>")
    html_body.append("<div class='stat'><div class='k'>Publish and monitor</div><div class='v'>Shareable output</div>"
                     "<div class='s'>Generate dashboards, weekly updates, CSV/JSON exports, and trend reports.</div></div>")
    html_body.append("</div>")
    html_body.append("</section>")

    html_body.append("<section id='templates'>")
    html_body.append("<div class='section-title'><div><h2>Create From Template</h2><p>Each template changes default sources and scoring categories.</p></div></div>")
    html_body.append("<div class='templates'>")
    templates = [
        ("Biomedical Science", "PubMed, bioRxiv, medRxiv. Disease relevance, method novelty, clinical translation."),
        ("Computer Science / AI", "arXiv, Semantic Scholar. Benchmarks, model architecture, code availability."),
        ("Climate Science", "CrossRef, arXiv, agency feeds. Regional signal, model update, policy relevance."),
        ("Chemistry", "CrossRef, PubMed, arXiv. Synthesis method, catalyst, assay, application."),
        ("Materials Science", "CrossRef, arXiv. Structure-property signal, fabrication, characterization."),
        ("Public Health", "PubMed, medRxiv, CDC/WHO feeds. Outbreak relevance, policy relevance, population scale."),
        ("Custom Field", "User-defined sources, terms, signals, weights, and export formats."),
    ]
    for title, desc in templates:
        html_body.append(f"<a class='template' href='#demo'><h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p></a>")
    html_body.append("</div>")
    html_body.append("</section>")

    html_body.append("<section id='create'>")
    html_body.append("<div class='section-title'><div><h2>Radar Builder</h2><p>Define the topic, sources, queries, signal categories, and weights.</p></div><span class='chip'><b>MVP flow</b> topic -> sources -> weights -> publish</span></div>")
    html_body.append("<div class='builder-grid'>")
    html_body.append("<div class='builder-main'>")
    html_body.append("<div class='builder-panel'><h3>1. Define the topic</h3><section class='controls' aria-label='Define topic'>")
    html_body.append("<div class='control wide'><label>Radar name</label><input type='text' value='AI Protein Design Radar'/></div>")
    html_body.append("<div class='control wide'><label>Research question</label><input type='text' value='What are the newest papers on generative models for protein engineering?'/></div>")
    html_body.append("</section></div>")

    html_body.append("<div class='builder-panel'><h3>2. Choose sources</h3><div class='checks'>")
    for source in ["PubMed", "bioRxiv", "medRxiv", "arXiv", "Semantic Scholar", "CrossRef", "Custom RSS feed", "Manual DOI list"]:
        html_body.append(f"<span>{html.escape(source)}</span>")
    html_body.append("</div></div>")

    html_body.append("<div class='builder-panel'><h3>3. Define search queries</h3><div class='mode-tabs'><span class='active'>Simple</span><span>Advanced</span></div>")
    html_body.append("<section class='controls' aria-label='Search query controls'>")
    html_body.append("<div class='control wide'><label>Main terms</label><textarea>protein design, generative models, diffusion models, protein engineering</textarea></div>")
    html_body.append("<div class='control wide'><label>Exclude terms</label><textarea>opinion, editorial, correction</textarea></div>")
    html_body.append("<div class='control full'><label>Advanced query preview</label><textarea>(\"protein design\" OR \"protein engineering\") AND (\"diffusion model\" OR \"generative model\" OR \"language model\")</textarea></div>")
    html_body.append("</section></div>")

    html_body.append("<div class='builder-panel'><h3>4. Define signal profile</h3><p class='muted'>What should ResearchRadar prioritize?</p><div class='checks'>")
    for sig in ["New method", "Benchmark or dataset", "Experimental validation", "Clinical/translational relevance", "Review article", "Open-source code", "High-impact journal", "Recent preprint"]:
        html_body.append(f"<span>{html.escape(sig)}</span>")
    html_body.append("</div><section class='controls' aria-label='Custom signal'>")
    html_body.append("<div class='control wide'><label>Custom research signal</label><input type='text' value='experimentally validated proteins'/></div>")
    html_body.append("<div class='control wide'><label>Priority terms</label><input type='text' value='wet lab validation, binding assay, structure prediction, functional assay'/></div>")
    html_body.append("<div class='control'><label>Weight</label><div class='checks'><span>High</span><span>Medium</span><span>Low</span></div></div>")
    html_body.append("</section></div>")

    html_body.append("<div class='builder-panel'><h3>5. Adjust weights</h3><div class='weights'>")
    for name, pct in [
        ("Recency", 70),
        ("Topic relevance", 90),
        ("Methods novelty", 70),
        ("Clinical relevance", 30),
        ("Open-source code available", 40),
        ("Review articles", 20),
    ]:
        html_body.append(f"<div class='weight-row'><span>{html.escape(name)}</span><div class='bar'><span style='width:{pct}%'></span></div><span>{pct}%</span></div>")
    html_body.append("</div></div>")
    html_body.append("</div>")

    html_body.append("<aside class='builder-side'>")
    html_body.append("<div class='builder-panel'><h3>Generated starter radar</h3><div class='yaml'>radar_name: Cancer Evolution and Therapy Resistance\nsources:\n  - PubMed\n  - bioRxiv\n  - medRxiv\nquery_set:\n  - \"cancer evolution\"\n  - \"therapy resistance\"\n  - \"clonal evolution\"\n  - \"tumor phylogeny\"\nsignal_profile:\n  high_priority:\n    terms:\n      - \"clonal selection\"\n      - \"subclonal expansion\"\n      - \"drug resistance\"\n      - \"minimal residual disease\"\n    weight: 2.5\n  methods:\n    terms:\n      - \"single-cell sequencing\"\n      - \"phylogenetics\"\n      - \"mutational signatures\"\n    weight: 1.5</div></div>")
    html_body.append("<div class='builder-panel'><h3>Create your own version</h3><p><b>Level 1</b><br/><span class='muted'>No-code web radar with private/public dashboard, digest, CSV, and BibTeX export.</span></p><p><b>Level 2</b><br/><span class='muted'>Power users edit YAML and run <span class='mono'>researchradar build</span>.</span></p><p><b>Level 3</b><br/><span class='muted'>Developers fork, deploy, and integrate custom APIs.</span></p></div>")
    html_body.append("<div class='builder-panel'><h3>Publish options</h3><div class='checks'><span>Save</span><span>Clone</span><span>Compare</span><span>GitHub Pages</span><span>Cloudflare Pages</span><span>Vercel</span><span>Docker</span></div></div>")
    html_body.append("</aside>")
    html_body.append("</div>")
    html_body.append("</section>")

    html_body.append("<section id='docs'>")
    html_body.append("<div class='section-title'><div><h2>Outputs And Exports</h2><p>Radars should be useful in the web app, at the command line, and inside academic workflows.</p></div></div>")
    html_body.append("<div class='grid'>")
    html_body.append("<div class='stat'><div class='k'>Downloads</div><div class='v'>Artifacts</div>"
                     "<div class='s'><a href='latest.json'>latest.json</a> · <a href='latest.md'>latest.md</a></div></div>")
    html_body.append("<div class='stat'><div class='k'>Ranking</div><div class='v'>Research Relevance Score</div>"
                     "<div class='s'>Topic priority + research signals + source metadata + recency + cross-domain bridge</div></div>")
    html_body.append("<div class='stat'><div class='k'>Scope</div><div class='v'>PubMed</div>"
                     "<div class='s'>Fetched via NCBI E-utilities; sorted by PubDate then re-ranked per theme</div></div>")
    html_body.append("<div class='stat'><div class='k'>Tip</div><div class='v'>Tune noise</div>"
                     "<div class='s'>Use <span class='mono'>--boosters</span>/<span class='mono'>--negatives</span> to widen/narrow</div></div>")
    html_body.append("</div>")
    html_body.append("</section>")

    # Quick nav
    html_body.append("<section id='demo'>")
    html_body.append("<div class='section-title'><div><h2>AI Protein Design Radar</h2><p>Example dashboard pattern: top papers, trends, authors, journals, methods, saved papers, and exports.</p></div>")
    html_body.append(f"<span class='chip'><b>Total hits</b> {total_hits}</span></div>")
    html_body.append("<div class='tabs'><span class='active'>Top Papers</span><span>Trends</span><span>Authors</span><span>Journals</span><span>Methods</span><span>Saved</span><span>Export</span></div>")
    html_body.append("<div class='insights'>")
    html_body.append("<div class='insight'><h3>Top signals this week</h3><ul><li>Diffusion models for enzyme design</li><li>Protein language models with wet-lab validation</li><li>New benchmark datasets for protein fitness prediction</li></ul></div>")
    html_body.append("<div class='insight'><h3>Emerging terms</h3><ul><li>protein diffusion model <span class='trend-up'>+42%</span></li><li>enzyme design <span class='trend-up'>+31%</span></li><li>antibody language model <span class='trend-up'>+28%</span></li><li>inverse folding <span class='trend-up'>+22%</span></li></ul></div>")
    html_body.append("<div class='insight'><h3>Field map</h3><div class='tree'>Protein design\n|-- Generative models\n|-- Structure prediction\n|-- Fitness landscapes\n|-- Antibody engineering\n|-- Enzyme design\n`-- Wet-lab validation</div></div>")
    html_body.append("<div class='insight'><h3>Saved paper tags</h3><div class='checks'><span>grant idea</span><span>read later</span><span>competitor</span><span>method to benchmark</span><span>possible collaborator</span></div></div>")
    html_body.append("<div class='insight'><h3>Tune by feedback</h3><p class='muted'>Relevant / Not relevant votes can suggest weight increases for lineage tracing, single-cell, phylogeny, or any repeated priority term.</p></div>")
    html_body.append("<div class='insight'><h3>Export everything</h3><div class='checks'><span>CSV</span><span>BibTeX</span><span>RIS</span><span>Markdown summary</span><span>Grant background</span><span>Weekly digest</span></div></div>")
    html_body.append("</div>")
    html_body.append("<div class='nav'>")
    for idx, block in enumerate(payload.get("sections", []), start=1):
        anchor = f"sec-{idx}"
        raw_label = block.get("label", "Section")
        label = html.escape(raw_label)
        cnt = int(block.get("count", 0) or 0)
        html_body.append(f"<a href='#{anchor}'>{label} <span class='mono'>({cnt})</span></a>")
    html_body.append("</div>")
    html_body.append("</section>")
    html_body.append("</header>")

    # Theme blocks
    for idx, block in enumerate(payload.get("sections", []), start=1):
        anchor = f"sec-{idx}"
        raw_label = block.get("label", "Section")
        label = html.escape(raw_label)
        cnt = int(block.get("count", 0) or 0)
        q = html.escape(block.get("query", ""))

        html_body.append(f"<section class='block' id='{anchor}'>")
        html_body.append("<div class='blockhead'>")
        html_body.append(f"<div class='blocktitle'><h2>{label}</h2><span class='count'>{cnt} result(s)</span></div>")
        html_body.append("</div>")

        if q:
            html_body.append("<details>")
            html_body.append("<summary>Show query</summary>")
            html_body.append(f"<div class='muted mono' style='margin-top:8px;white-space:pre-wrap'>{q}</div>")
            html_body.append("</details>")

        if not block.get("items"):
            html_body.append("<p class='muted' style='margin:10px 0 6px'>No new items in this window.</p>")
            html_body.append("</section>")
            continue

        for it in block.get("items", []):
            title = html.escape(it.get("title") or "(no title)")
            link = html.escape(it.get("link") or "#")
            meta_parts = [it.get("authors", ""), it.get("journal", ""), it.get("pubdate", "")]
            meta = " · ".join([html.escape(m) for m in meta_parts if m])
            snippet = html.escape(it.get("abstract_snippet", ""))
            raw_score = float(it.get("score", 0.0) or 0.0)
            score = html.escape(str(it.get("score", 0.0)))
            display_score = int(min(99, max(0, round(raw_score * 5.0))))
            signals = [html.escape(s) for s in it.get("signal_classes", [])]
            components = it.get("score_components", {})
            component_title = html.escape(", ".join(f"{k}: {v}" for k, v in components.items()))
            why_lines = [
                f"Matches topic: {raw_label}",
                f"Published within the last {int(payload['days'])} days",
            ]
            if signals:
                why_lines.append("Contains research signal: " + ", ".join(signals[:3]))
            if float(components.get("cross_domain", 0.0) or 0.0) > 0:
                why_lines.append("Connects multiple signal categories")
            if float(components.get("recency", 0.0) or 0.0) > 1.0:
                why_lines.append("Strong recency boost")

            html_body.append("<div class='card'>")
            html_body.append(
                f"<div class='t'><a href='{link}' target='_blank' rel='noopener'>{title}</a>"
                f"<span class='chip score score-pill' title='{component_title}'><b>Research Relevance Score</b> <span class='mono'>{display_score}</span></span></div>"
            )
            if meta:
                html_body.append(f"<div class='meta'>{meta}</div>")
            if signals:
                html_body.append("<div class='signals'>")
                for sig in signals:
                    html_body.append(f"<span class='chip'>{sig}</span>")
                html_body.append("</div>")
            if snippet:
                html_body.append(f"<div class='abs'>{snippet}</div>")
            html_body.append("<div class='why'><b>Why ranked highly</b><ul>")
            for reason in why_lines:
                html_body.append(f"<li>{html.escape(reason)}</li>")
            html_body.append("</ul></div>")
            html_body.append("<div class='actions'>")
            for action in ["Abstract", "Save", "Hide", "Relevant", "Not relevant", "Similar papers", "Export citation"]:
                html_body.append(f"<button class='btn small'>{html.escape(action)}</button>")
            html_body.append("</div>")
            html_body.append("</div>")

        html_body.append("</section>")

    html_body.append("<div class='footer'>Generated automatically from configured literature sources. Current demo source: PubMed via NCBI E-utilities. For informational use only.</div>")
    html_body.append("</body></html>")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write("".join(html_body))

    _write_product_pages(outdir_docs, payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1, help="Lookback window in days (default: 1)")
    ap.add_argument("--max", type=int, default=12, help="Max items per section (default: 12)")
    ap.add_argument("--docs-dir", default="docs", help="Docs output directory (default: docs)")
    ap.add_argument(
        "--boosters",
        type=int,
        default=6,
        help="How many booster terms to include per theme query (default: 6).",
    )
    ap.add_argument(
        "--negatives",
        type=int,
        default=6,
        help="How many negative terms to include per theme query (default: 6).",
    )
    args = ap.parse_args()

    # Rebuild queries with CLI knobs (so you can quickly tune noise in Actions)
    queries = {k: build_query(v, booster_strength=args.boosters, negative_strength=args.negatives) for k, v in THEMES.items()}

    # Date window (UTC for PubMed pdat filtering)
    end = dt.datetime.now(dt.timezone.utc).date()
    start = end - dt.timedelta(days=max(args.days, 1))
    mindate = start.strftime("%Y/%m/%d")
    maxdate = end.strftime("%Y/%m/%d")

    generated_at_local = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sections: List[Dict[str, Any]] = []
    for label, term in queries.items():
        try:
            pmids = esearch(term, mindate=mindate, maxdate=maxdate, retmax=args.max)
            time.sleep(0.34)  # be polite to NCBI
            details = efetch_details(pmids, theme_key=label)
            details = rank_and_trim(details, args.max)
            sections.append({"label": label, "query": term, "count": len(details), "items": details})
            time.sleep(0.34)
        except Exception as e:
            sections.append({"label": label, "query": term, "count": 0, "items": [], "error": str(e)})

    payload: Dict[str, Any] = {
        "generated_at_local": generated_at_local,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "days": args.days,
        "window_utc": {"mindate": mindate, "maxdate": maxdate},
        "ranking": "research_relevance_score(topic_priority + research_signal + source_metadata + recency + cross_domain)",
        "signal_ontology": {
            s.name: {"label": s.label, "weight": s.weight, "patterns": s.patterns}
            for s in SIGNAL_CLASSES
        },
        "themes": {k: {"priority": v.priority} for k, v in THEMES.items()},
        "sections": sections,
    }

    os.makedirs(args.docs_dir, exist_ok=True)
    write_outputs(args.docs_dir, payload)
    print(f"Wrote {args.docs_dir}/index.html, latest.json, latest.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
