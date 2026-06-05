from __future__ import annotations

import unittest

from backend.agent.candidate_scoring import score_candidates_locally
from backend.agent.candidate_store import load_candidates
from backend.agent.schemas import CandidateSearchStrategy, JDSignals
from backend.agent.validators import outreach_quality_validator, validate_boolean_query


class ValidatorTests(unittest.TestCase):
    def test_candidate_database_contains_at_least_five_unique_profiles(self) -> None:
        candidates = load_candidates()
        names = [candidate.candidate.full_name for candidate in candidates]

        self.assertGreaterEqual(len(candidates), 5)
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("Shuzhu Chen", names)

    def test_local_candidate_scoring_returns_all_candidates_sorted(self) -> None:
        candidates = load_candidates()
        signals = JDSignals(
            role_type="Finance Business Partner",
            required_skills=["FP&A", "Budgeting", "Forecasting", "Power BI"],
            seniority_indicators=["5+ years"],
            company_stage="Digital content business",
            missing_information=[],
            specific_detail="LATAM business reviews",
        )
        strategy = CandidateSearchStrategy(
            target_backgrounds=["Finance analyst", "FP&A"],
            target_companies=["Media", "Digital content"],
            keywords=["financial modeling", "variance analysis", "Power BI"],
            seniority="Mid to senior",
        )

        matches = score_candidates_locally(candidates, signals, strategy)
        scores = [match.match_score for match in matches]

        self.assertEqual(len(matches), len(candidates))
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(matches[0].full_name, "Sophia Martinez")

    def test_short_skill_does_not_match_longer_keyword_substring(self) -> None:
        candidates = load_candidates()
        signals = JDSignals(
            role_type="AI Full-Stack Software Engineer",
            required_skills=["Python", "React", "Node.js", "AWS", "RAG"],
            seniority_indicators=["full-time software development engineer"],
            company_stage="AI product company",
            missing_information=[],
            specific_detail="agentic AI applications",
        )
        strategy = CandidateSearchStrategy(
            target_backgrounds=["Full-stack engineer", "AI engineer", "Software engineer"],
            target_companies=["AI startups", "cloud software companies"],
            keywords=["Python", "React", "Node.js", "AWS", "LangChain", "RAG", "microservices"],
            seniority="Entry to mid",
        )

        shuzhu = next(
            match
            for match in score_candidates_locally(candidates, signals, strategy)
            if match.full_name == "Shuzhu Chen"
        )

        self.assertNotIn("R", shuzhu.matched_skills)

    def test_hiring_manager_notes_add_visible_preference_score(self) -> None:
        candidates = load_candidates()
        signals = JDSignals(
            role_type="Software Engineer",
            required_skills=["Python"],
            seniority_indicators=["full-time software development engineer"],
            company_stage="AI product company",
            missing_information=[],
            specific_detail="agentic AI applications",
        )
        strategy = CandidateSearchStrategy(
            target_backgrounds=["Software engineer"],
            target_companies=["AI startups", "cloud software companies"],
            keywords=["Python"],
            seniority="Entry to mid",
        )

        shuzhu = next(
            match
            for match in score_candidates_locally(
                candidates,
                signals,
                strategy,
                "Prioritize Kafka, Redis, MongoDB, and Tailwind CSS experience.",
            )
            if match.full_name == "Shuzhu Chen"
        )

        self.assertGreater(shuzhu.hiring_manager_score, 0)
        self.assertLessEqual(shuzhu.hiring_manager_score, 20)
        self.assertEqual(
            shuzhu.match_score,
            min(100, shuzhu.jd_match_score + shuzhu.hiring_manager_score),
        )
        self.assertIn("Kafka", shuzhu.matched_manager_preferences)

    def test_boolean_query_rejects_protected_class_filter(self) -> None:
        valid, note = validate_boolean_query("FP&A AND gender")

        self.assertFalse(valid)
        self.assertIn("gender", note)

    def test_outreach_requires_jd_specific_detail(self) -> None:
        signals = JDSignals(
            role_type="Finance Business Partner",
            required_skills=["FP&A", "Financial modeling"],
            seniority_indicators=["Minimum 5 years"],
            company_stage="Not stated",
            missing_information=["Compensation"],
            specific_detail="drive high quality content supply",
        )

        valid, errors = outreach_quality_validator(
            "Hi, your FP&A background looks relevant. Would you like to connect?",
            signals.specific_detail,
            "We partner with the business to drive high quality content supply.",
            signals,
        )

        self.assertFalse(valid)
        self.assertTrue(any("specific_detail" in error for error in errors))

    def test_outreach_rejects_generic_salesy_language(self) -> None:
        signals = JDSignals(
            role_type="Finance Business Partner",
            required_skills=["FP&A", "Power BI"],
            seniority_indicators=["Minimum 5 years"],
            company_stage="Not stated",
            missing_information=[],
            specific_detail="LATAM business reviews",
        )

        valid, errors = outreach_quality_validator(
            "Hi Alex, I came across your profile and was impressed by your background. "
            "You seem like a perfect fit for an exciting opportunity focused on LATAM business reviews.",
            signals.specific_detail,
            "This Finance BP role supports budget planning and LATAM business reviews.",
            signals,
        )

        self.assertFalse(valid)
        self.assertTrue(any("banned generic phrase" in error for error in errors))
        self.assertTrue(any("CTA" in error for error in errors))

    def test_outreach_accepts_warm_specific_low_pressure_message(self) -> None:
        signals = JDSignals(
            role_type="Finance Business Partner",
            required_skills=["FP&A", "Power BI"],
            seniority_indicators=["Minimum 5 years"],
            company_stage="Not stated",
            missing_information=[],
            specific_detail="LATAM business reviews",
        )

        valid, errors = outreach_quality_validator(
            "Hi Alex, your FP&A work maps well to LATAM business reviews. "
            "We’re hiring a Finance BP for budget planning across Brazil/Mexico. "
            "Open to a quick chat?",
            signals.specific_detail,
            "This Finance BP role supports budget planning and LATAM business reviews.",
            signals,
        )

        self.assertTrue(valid, errors)

    def test_outreach_requires_candidate_first_name_when_provided(self) -> None:
        signals = JDSignals(
            role_type="Finance Business Partner",
            required_skills=["FP&A", "Power BI"],
            seniority_indicators=["Minimum 5 years"],
            company_stage="Not stated",
            missing_information=[],
            specific_detail="LATAM business reviews",
        )

        valid, errors = outreach_quality_validator(
            "Hi Alex, your FP&A work maps well to LATAM business reviews. "
            "We’re hiring a Finance BP for budget planning across Brazil/Mexico. "
            "Open to a quick chat?",
            signals.specific_detail,
            "This Finance BP role supports budget planning and LATAM business reviews.",
            signals,
            candidate_first_name="Sophia",
        )

        self.assertFalse(valid)
        self.assertTrue(any("first name" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
