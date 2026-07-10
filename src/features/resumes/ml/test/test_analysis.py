import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis import (
    candidate_matches,
    keyword_coverage,
    load_normalization_dictionary,
    score_fit,
)


class AnalysisTest(unittest.TestCase):
    def test_dictionary_normalizes_aliases(self):
        dictionary = load_normalization_dictionary()
        aliases = dictionary["alias_to_skill"]
        self.assertEqual(aliases["postgres"]["canonical"], "PostgreSQL")
        self.assertEqual(aliases["restful apis"]["canonical"], "REST APIs")

    def test_keyword_coverage(self):
        self.assertGreater(keyword_coverage("Build REST APIs with PostgreSQL", "Designed REST APIs backed by PostgreSQL"), 0.5)

    def test_candidate_matching_uses_normalized_overlap(self):
        dictionary = load_normalization_dictionary()
        candidates = candidate_matches(
            [{"id": "req-1", "text": "Build RESTful APIs with Postgres", "type": "required skill"}],
            [{"id": "ev-1", "text": "Built REST APIs backed by PostgreSQL", "sourceSection": "Experience"}],
            dictionary,
        )
        self.assertEqual(candidates[0]["matches"][0]["evidenceId"], "ev-1")
        self.assertIn("PostgreSQL", candidates[0]["matches"][0]["normalizedSkillOverlap"])

    def test_candidate_matching_uses_validated_job_content_evidence_phrase(self):
        dictionary = load_normalization_dictionary()
        requirements = [
            {
                "id": "req-1",
                "text": "Design, build, and maintain scalable frontend experiences for complex product workflows while collaborating across teams",
                "evidence": "React workflow interfaces",
                "type": "responsibility",
                "importance": "required",
            },
        ]
        evidence_items = [
            {
                "id": "ev-1",
                "text": "Built React workflow interfaces for clinical trial teams and operational users.",
                "sourceSection": "Software Engineer, ClinMatchGO",
            },
        ]

        candidates = candidate_matches(requirements, evidence_items, dictionary)
        result = score_fit(requirements, evidence_items, candidates)

        self.assertEqual(result["requirements"][0]["evidenceStrength"], "direct evidence")
        self.assertTrue(result["generationAllowed"])

    def test_candidate_matching_uses_requirement_text_when_evidence_phrase_is_generic(self):
        dictionary = load_normalization_dictionary()
        requirements = [
            {
                "id": "req-1",
                "text": "Build React workflow interfaces for internal users",
                "evidence": "modern web applications",
                "type": "responsibility",
                "importance": "required",
            },
        ]
        evidence_items = [
            {
                "id": "ev-1",
                "text": "Built React workflow interfaces for clinical trial teams and operational users.",
                "sourceSection": "Software Engineer, ClinMatchGO",
            },
        ]

        candidates = candidate_matches(requirements, evidence_items, dictionary)
        result = score_fit(requirements, evidence_items, candidates)

        self.assertIn(
            result["requirements"][0]["evidenceStrength"],
            {"direct evidence", "adjacent evidence"},
        )
        self.assertTrue(result["generationAllowed"])

    def test_score_fit_classifies_gaps(self):
        result = score_fit(
            [
                {"id": "req-1", "text": "Build REST APIs", "type": "required skill", "importance": "required"},
                {"id": "req-2", "text": "Kubernetes operations", "type": "required skill", "importance": "required"},
            ],
            [{"id": "ev-1", "text": "Built REST APIs", "sourceSection": "Experience"}],
            [{"requirementId": "req-1", "matches": [{"evidenceId": "ev-1", "keywordCoverage": 1, "tfidfSimilarity": 0.8, "normalizedSkillOverlap": ["REST APIs"], "sectionHint": False, "score": 0.9}]}],
        )
        self.assertTrue(result["gaps"])
        self.assertEqual(result["requirements"][0]["evidenceStrength"], "direct evidence")

    def test_score_fit_uses_local_tfidf_as_semantic_similarity(self):
        result = score_fit(
            [{"id": "req-1", "text": "Design backend integrations", "type": "responsibility", "importance": "required"}],
            [{"id": "ev-1", "text": "Designed backend integration workflows", "sourceSection": "Experience"}],
            [{"requirementId": "req-1", "matches": [{"evidenceId": "ev-1", "keywordCoverage": 0.2, "tfidfSimilarity": 0.8, "normalizedSkillOverlap": [], "sectionHint": False, "score": 0.3}]}],
        )

        self.assertEqual(result["requirements"][0]["matches"][0]["semanticSimilarity"], 0.8)

    def test_score_fit_allows_generation_with_truthful_supported_subset(self):
        result = score_fit(
            [
                {"id": "req-1", "text": "Build REST APIs", "type": "required skill", "importance": "required"},
                {"id": "req-2", "text": "Operate Kubernetes", "type": "required skill", "importance": "required"},
                {"id": "req-3", "text": "Maintain data warehouses", "type": "responsibility", "importance": "required"},
            ],
            [{"id": "ev-1", "text": "Built REST APIs backed by PostgreSQL", "sourceSection": "Experience"}],
            [{"requirementId": "req-1", "matches": [{"evidenceId": "ev-1", "keywordCoverage": 1, "tfidfSimilarity": 0.8, "normalizedSkillOverlap": ["REST APIs"], "sectionHint": False, "score": 0.9}]}],
        )

        self.assertTrue(result["generationAllowed"])
        self.assertEqual(len(result["gaps"]), 2)

    def test_score_fit_blocks_generation_without_required_support(self):
        result = score_fit(
            [
                {"id": "req-1", "text": "Operate Kubernetes", "type": "required skill", "importance": "required"},
                {"id": "req-2", "text": "Build REST APIs", "type": "preferred skill", "importance": "preferred"},
            ],
            [{"id": "ev-1", "text": "Built REST APIs backed by PostgreSQL", "sourceSection": "Experience"}],
            [{"requirementId": "req-2", "matches": [{"evidenceId": "ev-1", "keywordCoverage": 1, "tfidfSimilarity": 0.8, "normalizedSkillOverlap": ["REST APIs"], "sectionHint": False, "score": 0.9}]}],
        )

        self.assertFalse(result["generationAllowed"])


if __name__ == "__main__":
    unittest.main()
