import json
import pathlib
import sys
from ast import literal_eval

src = pathlib.Path("/Users/keem.adorable@scalapay.com/scalapay/scalapay_mcp_kam/scalapay/scalapay_mcp_kam/results.json")
dst = src.with_suffix(".json.fixed")

# Read the whole file (Python-ish dict)
text = src.read_text(encoding="utf-8")

# Safely parse Python literals -> Python objects
data = literal_eval(text)

# Dump as strict JSON
dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote: {dst}")
