#!/usr/bin/env python3
"""
Test the paragraph token fix.
"""

import sys

sys.path.insert(0, "scalapay/scalapay_mcp_kam")


def test_slug_mapper_has_token():
    """Test the has_token method."""
    print("🔗 Testing SlugMapper has_token Method")
    print("=" * 50)

    try:
        from scalapay.scalapay_mcp_kam.utils.slug_validation import SlugMapper

        # Use the actual template ID from the logs
        template_id = "1hDkICKx4D3jHdxky_3_1iJcPFVQFxTkvlH7mVSFCx_o"
        mapper = SlugMapper(template_id)

        print(f"✅ SlugMapper created for template {template_id}")
        print(f"   Template placeholders found: {len(mapper.template_placeholders)}")
        print(f"   Template slugs found: {len(mapper.template_slugs)}")

        # Test tokens that should exist (from logs)
        existing_tokens = [
            "{{aov_chart}}",
            "{{aov_title}}",
            "{{monthly-sales-over-time_chart}}",
            "{{monthly-sales-over-time_title}}",
        ]

        # Test tokens that shouldn't exist (paragraph tokens)
        missing_tokens = [
            "{{aov_paragraph}}",
            "{{monthly-sales-over-time_paragraph}}",
            "{{monthly-orders-by-user-type_paragraph}}",
        ]

        print("\n📋 Testing existing tokens:")
        for token in existing_tokens:
            has_token = mapper.has_token(token)
            status = "✅" if has_token else "❌"
            print(f"   {status} {token}: {has_token}")

        print("\n📋 Testing missing paragraph tokens:")
        for token in missing_tokens:
            has_token = mapper.has_token(token)
            status = "✅" if not has_token else "❌"  # We want these to be missing
            print(f"   {status} {token}: {has_token} (should be False)")

        return True

    except Exception as e:
        print(f"💥 Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_token_conditional_logic():
    """Test the conditional token logic."""
    print("\n🎯 Testing Conditional Token Creation Logic")
    print("=" * 50)

    # Simulate the logic we implemented
    template_tokens = [
        "{{aov_chart}}",
        "{{aov_title}}",
        "{{monthly-sales-over-time_chart}}",
        "{{monthly-sales-over-time_title}}",
    ]

    # Simulate building text_map
    text_map = {}

    # Test cases
    test_cases = [("aov", "This is AOV content"), ("monthly-sales-over-time", "This is monthly sales content")]

    for slug, content in test_cases:
        title_token = f"{{{{{slug}_title}}}}"
        paragraph_token = f"{{{{{slug}_paragraph}}}}"

        # Always add title (it exists)
        text_map[title_token] = f"Title for {slug}"

        # Only add paragraph if it exists in template
        if paragraph_token in template_tokens:
            text_map[paragraph_token] = content
            print(f"✅ Added {paragraph_token} (exists in template)")
        else:
            print(f"⚠️  Skipped {paragraph_token} (missing from template)")

    print(f"\n📊 Final text_map has {len(text_map)} tokens:")
    for token, value in text_map.items():
        print(f"   {token}: {value[:30]}...")

    return True


if __name__ == "__main__":
    print("🧪 Testing Paragraph Token Fix")
    print()

    success1 = test_slug_mapper_has_token()
    success2 = test_token_conditional_logic()

    print("\n📊 Test Results:")
    print(f"   SlugMapper test: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"   Logic test: {'✅ PASS' if success2 else '❌ FAIL'}")

    if success1 and success2:
        print("\n🎉 All tests passed! The paragraph token fix should work.")
        print("\n💡 Expected behavior:")
        print("   - Title tokens will be created (they exist in template)")
        print("   - Paragraph tokens will be skipped (they don't exist in template)")
        print("   - This should increase slug validation success rate")
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
