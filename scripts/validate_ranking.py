"""Compute ranking metrics for ResearchRadar validation datasets.

Input CSV columns:
case_study,method,rank,relevance

Relevance should be 0, 1, or 2. Ranks are 1-based. The script reports
Precision@10, Precision@25, Recall@50, and nDCG@10 by case study and method.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class RankedPaper:
    case_study: str
    method: str
    rank: int
    relevance: int


def load_rows(path: str) -> List[RankedPaper]:
    rows: List[RankedPaper] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"case_study", "method", "rank", "relevance"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        for raw in reader:
            rows.append(
                RankedPaper(
                    case_study=raw["case_study"].strip(),
                    method=raw["method"].strip(),
                    rank=int(raw["rank"]),
                    relevance=int(raw["relevance"]),
                )
            )
    return rows


def precision_at(items: List[RankedPaper], k: int, threshold: int = 1) -> float:
    top = sorted(items, key=lambda item: item.rank)[:k]
    if not top:
        return 0.0
    return sum(1 for item in top if item.relevance >= threshold) / len(top)


def recall_at(items: List[RankedPaper], k: int, threshold: int = 1) -> float:
    all_relevant = sum(1 for item in items if item.relevance >= threshold)
    if all_relevant == 0:
        return 0.0
    top = sorted(items, key=lambda item: item.rank)[:k]
    return sum(1 for item in top if item.relevance >= threshold) / all_relevant


def dcg(relevances: Iterable[int]) -> float:
    return sum((2**rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(relevances))


def ndcg_at(items: List[RankedPaper], k: int) -> float:
    ranked = sorted(items, key=lambda item: item.rank)[:k]
    observed = dcg(item.relevance for item in ranked)
    ideal = dcg(sorted((item.relevance for item in items), reverse=True)[:k])
    if ideal == 0.0:
        return 0.0
    return observed / ideal


def group_rows(rows: Iterable[RankedPaper]) -> Dict[Tuple[str, str], List[RankedPaper]]:
    grouped: DefaultDict[Tuple[str, str], List[RankedPaper]] = defaultdict(list)
    for row in rows:
        grouped[(row.case_study, row.method)].append(row)
    return dict(grouped)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="Validation CSV with case_study, method, rank, relevance columns.")
    args = parser.parse_args()

    rows = load_rows(args.csv_path)
    print("case_study,method,precision_at_10,precision_at_25,recall_at_50,ndcg_at_10")
    for (case_study, method), items in sorted(group_rows(rows).items()):
        print(
            ",".join(
                [
                    case_study,
                    method,
                    f"{precision_at(items, 10):.3f}",
                    f"{precision_at(items, 25):.3f}",
                    f"{recall_at(items, 50):.3f}",
                    f"{ndcg_at(items, 10):.3f}",
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
