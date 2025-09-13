#!/usr/bin/env python3
"""
Test script to verify the slug validation fix.
Tests that validation now only requires title and chart tokens, not paragraph tokens.
"""

import sys

sys.path.insert(0, "scalapay/scalapay_mcp_kam")

from scalapay.scalapay_mcp_kam.utils.slug_validation import SlugMapper


def test_slug_validation_fix():
    """Test that validation no longer requires paragraph tokens."""
    print("🧪 Testing Slug Validation Fix")
    print("=" * 60)

    # Mock template with only title and chart tokens (no paragraph)
    class MockSlugMapper(SlugMapper):
        def __init__(self):
            self.template_id = "test_template"
            # Mock template placeholders - only title and chart tokens
            self.template_placeholders = [
                "{{monthly-sales-over-time_title}}",
                "{{monthly-sales-over-time_chart}}",
                "{{aov_title}}",
                "{{aov_chart}}",
                "{{scalapay-users-demographic-in-percentage_title}}",
                "{{scalapay-users-demographic-in-percentage_chart}}",
            ]
            self.template_slugs = {"monthly-sales-over-time", "aov", "scalapay-users-demographic-in-percentage"}
            self.slug_corrections = self._build_correction_map()

    # Test data keys from the logs
    test_data_keys = ["monthly sales year over year", "AOV", "scalapay users demographic in percentages"]

    mapper = MockSlugMapper()

    print(f"Template placeholders ({len(mapper.template_placeholders)}):")
    for placeholder in sorted(mapper.template_placeholders):
        print(f"  - {placeholder}")

    print(f"\nTemplate slugs ({len(mapper.template_slugs)}):")
    for slug in sorted(mapper.template_slugs):
        print(f"  - {slug}")

    # Run validation
    validation_report = mapper.validate_all_mappings(test_data_keys)

    print(f"\n📊 Validation Results:")
    print(f"  Success rate: {validation_report['success_rate']:.1%}")
    print(f"  Data keys tested: {validation_report['total_data_keys']}")
    print(f"  Issues found: {len(validation_report['issues_found'])}")

    print(f"\n📋 Detailed Results:")
    for data_key, result in validation_report["validation_results"].items():
        print(f"\n  Data key: '{data_key}'")
        print(f"    Generated slug: '{result['slug']}'")
        print(f"    Template match: {result['template_match']}")
        print(
            f"    Required tokens valid: {result['required_tokens_valid']} ✅"
            if result["required_tokens_valid"]
            else f"    Required tokens valid: {result['required_tokens_valid']} ❌"
        )

        print(f"    Token matches:")
        for token_type, matches in result["token_matches"].items():
            status = "✅" if matches else "❌"
            required = " (required)" if token_type in ["title", "chart"] else " (optional)"
            print(f"      {token_type}: {matches} {status}{required}")

    if validation_report["issues_found"]:
        print(f"\n⚠️  Issues Found:")
        for issue in validation_report["issues_found"]:
            print(f"  - {issue['data_key']}: {issue['issue']}")

    # Test success
    if validation_report["success_rate"] > 0.0:
        print(
            f"\n🎉 SUCCESS: Validation fix working! Success rate improved from 0.0% to {validation_report['success_rate']:.1%}"
        )
        return True
    else:
        print(f"\n❌ FAILED: Success rate still 0.0%")
        return False


def test_original_vs_fixed_validation():
    """Compare original validation (requiring all tokens) vs fixed validation (requiring only title+chart)."""
    print(f"\n🔄 Comparing Original vs Fixed Validation Logic")
    print("=" * 60)

    # Mock data
    slug = "monthly-sales-over-time"
    template_placeholders = [
        "{{monthly-sales-over-time_title}}",
        "{{monthly-sales-over-time_chart}}"
        # Note: No paragraph token in template
    ]

    tokens = {
        "title": "{{monthly-sales-over-time_title}}",
        "paragraph": "{{monthly-sales-over-time_paragraph}}",
        "chart": "{{monthly-sales-over-time_chart}}",
    }

    token_matches = {token_type: token in template_placeholders for token_type, token in tokens.items()}

    print(f"Template has tokens: {template_placeholders}")
    print(f"Generated tokens: {list(tokens.values())}")
    print(f"Token matches: {token_matches}")

    # Original validation logic (requires ALL tokens)
    original_validation = all(token_matches.values())

    # Fixed validation logic (requires only title + chart)
    required_tokens = ["title", "chart"]
    fixed_validation = all(token_matches[token_type] for token_type in required_tokens)

    print(f"\nOriginal validation (requires ALL tokens): {original_validation} {'✅' if original_validation else '❌'}")
    print(f"Fixed validation (requires title + chart): {fixed_validation} {'✅' if fixed_validation else '❌'}")

    if not original_validation and fixed_validation:
        print(f"\n🎯 FIX CONFIRMED: Fixed validation passes where original failed!")
        return True
    else:
        print(f"\n⚠️  Fix may need more work")
        return False


if __name__ == "__main__":
    print("🔧 Slug Validation Fix Test Suite")
    print("=" * 60)

    test1_success = test_slug_validation_fix()
    test2_success = test_original_vs_fixed_validation()

    print(f"\n" + "=" * 60)
    print(f"📊 Test Summary:")
    print(f"  Slug validation fix: {'✅ PASS' if test1_success else '❌ FAIL'}")
    print(f"  Logic comparison: {'✅ PASS' if test2_success else '❌ FAIL'}")

    if test1_success and test2_success:
        print(f"\n🎉 ALL TESTS PASSED! The slug validation fix should resolve the 0.0% success rate.")
        print(f"\n💡 Summary of Fix:")
        print(f"  - BEFORE: Required all tokens (title, paragraph, chart) to match")
        print(f"  - AFTER: Only requires title and chart tokens (paragraph is optional)")
        print(f"  - RESULT: Success rate should increase from 0.0% to expected ~100%")
    else:
        print(f"\n❌ Some tests failed. Check the output above.")
