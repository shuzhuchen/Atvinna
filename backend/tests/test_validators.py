from __future__ import annotations

import inspect
import unittest

import backend.agent.candidate_scoring as candidate_scoring
from backend.agent.candidate_scoring import interpret_match_score, score_candidates_locally
from backend.agent.candidate_store import load_candidates
from backend.agent.prompts import search_strategy_prompt
from backend.agent.schemas import CandidateSearchStrategy, JDSignals
from backend.agent.validators import (
    detect_recruiting_bias,
    outreach_quality_validator,
    validate_boolean_query,
)


class ValidatorTests(unittest.TestCase):
    def test_scoring_logic_does_not_hardcode_profession_specific_vocabulary(self) -> None:
        source = inspect.getsource(candidate_scoring._candidate_preference_vocabulary)

        profession_specific_terms = [
            "React",
            "AWS",
            "Kafka",
            "FP&A",
            "Power BI",
            "RAG",
            "microservices",
        ]
        for term in profession_specific_terms:
            self.assertNotIn(term, source)

    def test_search_strategy_prompt_requires_level_plus_yoe_when_available(self) -> None:
        prompt = search_strategy_prompt(
            JDSignals(
                role_type="Backend Engineer",
                required_skills=["Python"],
                seniority_indicators=["Minimum 5 years of backend engineering experience"],
                seniority_level="senior",
                company_stage="AI startup",
                missing_information=[],
                specific_detail="backend engineering experience",
            ).model_dump_json()
        )

        self.assertIn('Format seniority as "level, yoe"', prompt)
        self.assertIn('"senior, 5+ years"', prompt)
        self.assertIn("no YOE stated", prompt)
        self.assertIn("do not invent years", prompt)

    def test_interpret_match_score_boundaries(self) -> None:
        self.assertEqual(
            interpret_match_score(95),
            {
                "match_level": "Recruiter Screen",
                "recommendation": "Strong enough for recruiter outreach",
            },
        )
        self.assertEqual(
            interpret_match_score(82),
            {
                "match_level": "Recruiter Screen",
                "recommendation": "Strong enough for recruiter outreach",
            },
        )
        self.assertEqual(
            interpret_match_score(75),
            {
                "match_level": "Potential Match",
                "recommendation": "Review before outreach",
            },
        )
        self.assertEqual(
            interpret_match_score(65),
            {
                "match_level": "Potential Match",
                "recommendation": "Review before outreach",
            },
        )
        self.assertEqual(
            interpret_match_score(59),
            {
                "match_level": "Consider",
                "recommendation": "Possible fit with gaps",
            },
        )
        self.assertEqual(
            interpret_match_score(48),
            {
                "match_level": "Low Match",
                "recommendation": "Unlikely fit",
            },
        )
        self.assertEqual(
            interpret_match_score(11),
            {
                "match_level": "Not Recommended",
                "recommendation": "Do not prioritize",
            },
        )

    def test_candidate_database_contains_at_least_five_unique_profiles(self) -> None:
        candidates = load_candidates()
        names = [candidate.candidate.full_name for candidate in candidates]

        self.assertGreaterEqual(len(candidates), 5)
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("Shuzhu Chen", names)

    def test_local_candidate_scoring_returns_all_candidates_sorted(self) -> None:
        candidates = load_candidates()
        signals = JDSignals(
            role_type="Frontend Engineer Intern",
            required_skills=["React", "TypeScript", "Tailwind CSS", "REST APIs", "Accessibility"],
            related_skill_aliases={
                "React": ["React.js"],
                "REST APIs": ["API integration"],
                "Accessibility": ["a11y", "accessible UI"],
            },
            adjacent_backgrounds=["Frontend Engineer Intern", "Student Web Developer", "Frontend Engineer"],
            seniority_indicators=["intern", "new grad"],
            seniority_level="intern",
            company_stage="SaaS product",
            missing_information=[],
            specific_detail="creator analytics dashboard",
        )
        strategy = CandidateSearchStrategy(
            target_backgrounds=["Frontend Engineer Intern", "Student Web Developer", "Frontend Engineer"],
            target_companies=["SaaS", "creator tools", "product companies"],
            keywords=["React", "TypeScript", "Tailwind CSS", "REST APIs", "Accessibility", "Figma"],
            seniority="Intern/New grad",
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

    def test_match_score_requires_core_skill_and_background_coverage_for_90_plus(self) -> None:
        candidates = load_candidates()
        signals = JDSignals(
            role_type="AI Full-Stack Software Engineer",
            required_skills=["Python", "React", "Node.js", "AWS", "Kafka", "MongoDB", "Redis", "RESTful APIs"],
            seniority_indicators=["full-time software development engineer"],
            company_stage="AI product company",
            missing_information=[],
            specific_detail="agentic AI applications",
        )
        strategy = CandidateSearchStrategy(
            target_backgrounds=["Full-stack engineer", "AI engineer", "Software engineer"],
            target_companies=["AI startups", "cloud software companies"],
            keywords=["Python", "React", "Node.js", "AWS", "Kafka", "MongoDB", "Redis", "microservices"],
            seniority="Entry to mid",
        )

        matches = score_candidates_locally(
            candidates,
            signals,
            strategy,
            "Prioritize Kafka, Redis, MongoDB, and Tailwind CSS experience.",
        )
        shuzhu = next(match for match in matches if match.full_name == "Shuzhu Chen")
        maya = next(match for match in matches if match.full_name == "Maya Chen")

        self.assertGreaterEqual(shuzhu.match_score, 90)
        self.assertLess(maya.match_score, 75)

    def test_dynamic_aliases_and_adjacent_backgrounds_improve_general_matching(self) -> None:
        candidates = load_candidates()
        signals = JDSignals(
            role_type="Full Stack Engineer Intern",
            required_skills=["React", "REST APIs", "AWS"],
            related_skill_aliases={
                "React": ["React.js", "ReactJS"],
                "REST APIs": ["RESTful APIs", "API development"],
                "AWS": ["AWS Lambda", "AWS S3", "AWS Amplify"],
            },
            adjacent_backgrounds=["AI/ML Full-Stack Engineer", "Software Developer"],
            seniority_indicators=["intern"],
            seniority_level="intern",
            company_stage="Not stated",
            missing_information=[],
            specific_detail="content optimization systems",
        )
        strategy = CandidateSearchStrategy(
            target_backgrounds=["Full Stack Engineer Intern"],
            target_companies=["software product teams"],
            keywords=["React", "REST APIs", "AWS"],
            seniority="Intern",
        )

        shuzhu = next(
            match
            for match in score_candidates_locally(candidates, signals, strategy)
            if match.full_name == "Shuzhu Chen"
        )

        self.assertGreaterEqual(shuzhu.match_score, 90)
        self.assertIn("React", shuzhu.matched_skills)
        self.assertIn("REST APIs", shuzhu.matched_skills)
        self.assertIn("AWS", shuzhu.matched_skills)
        self.assertNotIn("AWS Lambda", shuzhu.matched_skills)

    def test_low_score_fit_reason_does_not_claim_role_match(self) -> None:
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
            target_backgrounds=["Finance Business Partner", "FP&A"],
            target_companies=["Media", "Digital content"],
            keywords=["financial modeling", "variance analysis", "Power BI"],
            seniority="Mid to senior",
        )

        low_match = next(
            match
            for match in score_candidates_locally(candidates, signals, strategy)
            if match.match_score < 50
        )

        self.assertNotIn("matches the Finance Business Partner need", low_match.fit_reason)
        self.assertTrue(
            low_match.fit_reason.startswith("Limited alignment:")
            or low_match.fit_reason.startswith("Not recommended because")
        )

    def test_boolean_query_rejects_protected_class_filter(self) -> None:
        result = validate_boolean_query("FP&A AND gender")

        self.assertFalse(result["is_valid"])
        self.assertTrue(any("gender" in warning for warning in result["warnings"]))

    def test_boolean_query_validator_accepts_structured_valid_query(self) -> None:
        result = validate_boolean_query('("Software Engineer" OR "Full-Stack Engineer") AND (Python OR React)')

        self.assertTrue(result["is_valid"], result)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["suggestions"], [])

    def test_boolean_query_validator_flags_syntax_and_breadth_issues(self) -> None:
        result = validate_boolean_query('(Python AND AND ""')

        self.assertFalse(result["is_valid"])
        self.assertTrue(any("balanced" in warning for warning in result["warnings"]))
        self.assertTrue(any("empty quotes" in warning for warning in result["warnings"]))
        self.assertTrue(any("repeated operator" in warning for warning in result["warnings"]))
        self.assertGreater(len(result["suggestions"]), 0)

    def test_boolean_query_validator_flags_too_broad_query(self) -> None:
        result = validate_boolean_query("Python")

        self.assertFalse(result["is_valid"])
        self.assertTrue(any("AND or OR" in warning for warning in result["warnings"]))
        self.assertTrue(any("too broad" in warning for warning in result["warnings"]))

    def test_bias_detection_flags_risky_recruiting_terms(self) -> None:
        strategy = CandidateSearchStrategy(
            target_backgrounds=["Software Engineer"],
            target_companies=["Google"],
            keywords=["Python", "React"],
            seniority="Recent grad only",
        )

        result = detect_recruiting_bias(
            job_description="We need a young, energetic digital native from Ivy League only.",
            boolean_query='("Software Engineer" AND "native English speaker") AND "FAANG only"',
            search_strategy=strategy,
            outreach_message="Hi Alex, this aggressive team needs a dominant builder. Open to a quick chat?",
        )

        self.assertTrue(result["has_warning"])
        self.assertTrue(any("age-coded" in warning for warning in result["warnings"]))
        self.assertTrue(any("gender-coded" in warning for warning in result["warnings"]))
        self.assertTrue(any("nationality/language" in warning for warning in result["warnings"]))
        self.assertTrue(any("school prestige" in warning for warning in result["warnings"]))
        self.assertTrue(any("overly narrow" in warning for warning in result["warnings"]))

    def test_bias_detection_allows_role_relevant_language(self) -> None:
        strategy = CandidateSearchStrategy(
            target_backgrounds=["Full-stack engineer", "AI engineer"],
            target_companies=["AI startups", "cloud software companies", "data infrastructure teams"],
            keywords=["Python", "React", "AWS"],
            seniority="Mid-level",
        )

        result = detect_recruiting_bias(
            job_description="Build AI workflow tools with Python, React, and AWS.",
            boolean_query='("Full-stack engineer" OR "AI engineer") AND (Python OR React OR AWS)',
            search_strategy=strategy,
            outreach_message="Hi Shuzhu, your Python and React work maps well to AI workflow tools. Open to a quick chat?",
        )

        self.assertFalse(result["has_warning"], result)
        self.assertEqual(result["warnings"], [])

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
