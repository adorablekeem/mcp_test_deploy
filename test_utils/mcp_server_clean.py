#!/usr/bin/env python3
"""
MCP Server startup script with warning fixes applied.
"""

import warnings
import os

# Suppress all the MCP warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic.*")
warnings.filterwarnings("ignore", message=".*__fields__ attribute is deprecated.*")  
warnings.filterwarnings("ignore", message=".*PydanticDeprecatedSince20.*")
warnings.filterwarnings("ignore", message=".*datetime.datetime.utcnow.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*was never awaited.*")

# Set environment variables
os.environ["PYTHONWARNINGS"] = "ignore::DeprecationWarning,ignore::PydanticDeprecatedSince20,ignore::RuntimeWarning"

# Now import and run the MCP server
if __name__ == "__main__":
    from scalapay.scalapay_mcp_kam.mcp_server import main
    main()
