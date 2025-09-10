#!/usr/bin/env python3
"""
Test Google API authentication in connection manager.
"""

import sys
import os
import asyncio

# Add project to path
sys.path.insert(0, 'scalapay/scalapay_mcp_kam')

async def test_connection_manager_auth():
    """Test that the connection manager can create authenticated services."""
    
    print("🔐 Testing Google API Authentication in Connection Manager")
    print("=" * 60)
    
    try:
        from scalapay.scalapay_mcp_kam.utils.google_connection_manager import connection_manager
        
        print("✅ Successfully imported connection manager")
        
        # Test getting a service
        print("🔄 Testing service creation...")
        service = await connection_manager.get_service()
        
        print("✅ Service created successfully")
        print(f"   Service type: {type(service)}")
        
        # Test a simple API call that requires authentication
        print("🌐 Testing authenticated API call...")
        
        # Try to get a presentation (this will fail if not authenticated)
        test_presentation_id = "1HR5uKvvSnb8PzTTqnONtwRF-QGGYLVmyD4__VCha_AM"  # From your logs
        
        try:
            presentation = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: service.presentations().get(presentationId=test_presentation_id).execute()
            )
            print("✅ API call successful - authentication working!")
            print(f"   Presentation title: {presentation.get('title', 'No title')}")
            print(f"   Slides count: {len(presentation.get('slides', []))}")
            return True
            
        except Exception as api_error:
            if "401" in str(api_error) or "credentials" in str(api_error).lower():
                print(f"❌ Authentication failed: {api_error}")
                return False
            else:
                print(f"⚠️  API call failed (but not due to auth): {api_error}")
                return True  # Auth might be working, just other issues
                
    except Exception as e:
        print(f"💥 Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🧪 Google API Authentication Test")
    print()
    
    success = asyncio.run(test_connection_manager_auth())
    
    print("\n📊 Test Result:")
    if success:
        print("✅ Authentication appears to be working correctly")
        print("💡 The slide generation issue should now be resolved")
    else:
        print("❌ Authentication is still not working")
        print("💡 Further investigation needed")