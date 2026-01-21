#!/usr/bin/env python3
"""
Daily PubMed Watch — Viromics / Metagenomics edition

- Pulls the last N days of PubMed hits for a small set of queries
- Builds docs/latest.json, docs/latest.md, docs/index.html
- Designed for GitHub Actions + GitHub Pages (static)

Usage:
  python scripts/daily_pubmed_watch.py --days 1 --max 12
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Tuple


DEFAULT_QUERIES: Dict[str, str] = {
    # Career-aligned themes
    "Urban/Wastewater virome": '(virome OR "viral metagenomics") AND (wastewater OR sewage OR "built environment" OR urban)',
    "Metagenomics methods": 'metagenomics AND (benchmark* OR pipeline OR "quality control" OR assembly OR classification)',
    "Influenza evolution": '(influenza OR flu) AND (evolution OR "positive selection" OR "antigenic drift" OR clade)',
    "H5N1 / avian influenza": 'H5N1 OR "highly pathogenic avian influenza" OR HPAI',
    "Human virome": '"human virome" OR "gut virome" OR "virome atlas"',
    "AMR metagenomics": '("antimicrobial resistance" OR AMR) AND metagenomics',
}

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "daily-pubmed-watch/1.0"})
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
    pmids = [node.text for node in root.findall(".//IdList/Id") if node.text]
    return pmids


def efetch_details(pmids: List[str]) -> List[Dict[str, Any]]:
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
        abstract = (article.findtext(".//Abstract/AbstractText") or "").strip()

        journal = (article.findtext(".//Journal/Title") or "").strip()
        year = (article.findtext(".//PubDate/Year") or "").strip()
        pubdate_medline = (article.findtext(".//PubDate/MedlineDate") or "").strip()
        pubdate = year or pubdate_medline or ""

        # Build a stable PubMed link
        link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

        # First 6 authors (clean + readable)
        authors = []
        for a in article.findall(".//AuthorList/Author")[:6]:
            last = (a.findtext("LastName") or "").strip()
            fore = (a.findtext("ForeName") or "").strip()
            if last and fore:
                authors.append(f"{fore} {last}")
            elif last:
                authors.append(last)
        author_str = ", ".join(authors)

        items.append(
            {
                "pmid": pmid,
                "title": title,
                "authors": author_str,
                "journal": journal,
                "pubdate": pubdate,
                "link": link,
                "abstract_snippet": abstract[:260] + ("…" if len(abstract) > 260 else ""),
            }
        )
    return items


def rank_and_trim(items: List[Dict[str, Any]], max_items: int) -> List[Dict[str, Any]]:
    # PubMed already returned by pub date; just trim.
    return items[:max_items]


def write_outputs(outdir_docs: str, payload: Dict[str, Any]) -> None:
    # JSON
    json_path = f"{outdir_docs}/latest.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # Markdown
    md_path = f"{outdir_docs}/latest.md"
    lines = []
    lines.append(f"# Daily PubMed Watch (Viromics / Metagenomics)\n")
    lines.append(f"**Updated:** {payload['generated_at_local']}  \n")
    lines.append(f"**Window:** last {payload['days']} day(s)\n")
    for block in payload["sections"]:
        lines.append(f"\n## {block['label']} — {block['count']} result(s)\n")
        for it in block["items"]:
            title = it["title"] or "(no title)"
            lines.append(f"- **[{title}]({it['link']})**  ")
            meta = " · ".join([x for x in [it["authors"], it["journal"], it["pubdate"]] if x])
            if meta:
                lines.append(f"  {meta}  ")
            if it["abstract_snippet"]:
                lines.append(f"  _{it['abstract_snippet']}_")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    # HTML page (simple, self-contained)
    html_path = f"{outdir_docs}/index.html"
    html_body = []
    html_body.append("<!doctype html><html><head><meta charset='utf-8'/>")
    html_body.append("<meta name='viewport' content='width=device-width,initial-scale=1'/>")
    html_body.append("<title>Daily PubMed Watch</title>")
    html_body.append("""
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:980px;margin:40px auto;padding:0 16px;line-height:1.55;color:#222}
  .muted{color:#666}
  .card{border:1px solid #e6e6e6;border-radius:14px;padding:14px 16px;margin:12px 0;box-shadow:0 4px 16px rgba(0,0,0,.06)}
  a{color:#0b57d0;text-decoration:none} a:hover{text-decoration:underline}
  h1{margin-bottom:4px} h2{margin-top:26px}
  .tag{display:inline-block;background:#f3f3f3;border-radius:999px;padding:3px 10px;font-size:.85em;margin-left:8px;color:#444}
</style>
""")
    html_body.append("</head><body>")
    html_body.append("<h1>Daily PubMed Watch <span class='tag'>viromics • metagenomics • evo</span></h1>")
    html_body.append(f"<p class='muted'><strong>Updated:</strong> {html.escape(payload['generated_at_local'])} "
                     f" · <strong>Window:</strong> last {payload['days']} day(s) "
                     f" · <a href='latest.json'>latest.json</a> · <a href='latest.md'>latest.md</a></p>")

    for block in payload["sections"]:
        html_body.append(f"<h2>{html.escape(block['label'])} <span class='tag'>{block['count']} results</span></h2>")
        if not block["items"]:
            html_body.append("<p class='muted'>No new items in this window.</p>")
            continue
        for it in block["items"]:
            title = html.escape(it["title"] or "(no title)")
            link = html.escape(it["link"] or "#")
            meta_parts = [it.get("authors",""), it.get("journal",""), it.get("pubdate","")]
            meta = " · ".join([html.escape(m) for m in meta_parts if m])
            snippet = html.escape(it.get("abstract_snippet",""))
            html_body.append("<div class='card'>")
            html_body.append(f"<div><a href='{link}' target='_blank' rel='noopener'><strong>{title}</strong></a></div>")
            if meta:
                html_body.append(f"<div class='muted' style='margin-top:6px'>{meta}</div>")
            if snippet:
                html_body.append(f"<div class='muted' style='margin-top:10px'>{snippet}</div>")
            html_body.append("</div>")
    html_body.append("<hr style='border:none;border-top:1px solid #eee;margin:28px 0'/>")
    html_body.append("<p class='muted'>Generated automatically from PubMed via NCBI E-utilities. "
                     "For informational use only.</p>")
    html_body.append("</body></html>")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write("".join(html_body))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1, help="Lookback window in days (default: 1)")
    ap.add_argument("--max", type=int, default=12, help="Max items per section (default: 12)")
    ap.add_argument("--docs-dir", default="docs", help="Docs output directory (default: docs)")
    args = ap.parse_args()

    # Date window (UTC for PubMed pdat filtering)
    end = dt.datetime.utcnow().date()
    start = end - dt.timedelta(days=max(args.days, 1))

    mindate = start.strftime("%Y/%m/%d")
    maxdate = end.strftime("%Y/%m/%d")

    generated_at_local = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sections = []
    for label, term in DEFAULT_QUERIES.items():
        try:
            pmids = esearch(term, mindate=mindate, maxdate=maxdate, retmax=args.max)
            time.sleep(0.34)  # be polite to NCBI
            details = efetch_details(pmids)
            details = rank_and_trim(details, args.max)
            sections.append({"label": label, "query": term, "count": len(details), "items": details})
            time.sleep(0.34)
        except Exception as e:
            sections.append({"label": label, "query": term, "count": 0, "items": [], "error": str(e)})

    payload = {
        "generated_at_local": generated_at_local,
        "generated_at_utc": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "days": args.days,
        "window_utc": {"mindate": mindate, "maxdate": maxdate},
        "sections": sections,
    }

    # Ensure docs dir exists
    import os
    os.makedirs(args.docs_dir, exist_ok=True)

    write_outputs(args.docs_dir, payload)
    print(f"Wrote {args.docs_dir}/index.html, latest.json, latest.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
