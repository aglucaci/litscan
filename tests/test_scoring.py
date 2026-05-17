import datetime as dt
import unittest

from scripts.daily_pubmed_watch_v2 import score_paper


class ScoringTests(unittest.TestCase):
    def test_cross_domain_research_signals_are_tagged_and_scored(self) -> None:
        result = score_paper(
            title="Immune escape and positive selection in viral genomic surveillance",
            abstract=(
                "We estimate dN/dS with codon models, reconstruct a phylogenetic tree, "
                "and analyze wastewater genomic surveillance during an outbreak."
            ),
            theme_key="Selection & codon models",
            published_date=dt.datetime.now(dt.timezone.utc),
            venue="Molecular Biology and Evolution",
        )

        self.assertGreater(result["score"], 10.0)
        self.assertIn("Selection", result["signal_classes"])
        self.assertIn("Viral evolution", result["signal_classes"])
        self.assertIn("Metagenomics / surveillance", result["signal_classes"])
        self.assertIn("research_signal", result["components"])
        self.assertGreater(result["components"]["cross_domain"], 0.0)


if __name__ == "__main__":
    unittest.main()
