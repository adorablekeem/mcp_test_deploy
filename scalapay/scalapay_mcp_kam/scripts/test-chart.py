from charts_from_results import generate_all_charts_from_results
import json
PATH = "/Users/keem.adorable@scalapay.com/scalapay/scalapay_mcp_kam/scalapay/scalapay_mcp_kam/raw_alfred_output.txt"


with open(PATH, "r", encoding="utf-8") as f:
    raw_debug = f.read()  # <-- keep as string (single quotes are fine)


if __name__ == "__main__":
    summary = generate_all_charts_from_results(
        results_obj_or_str=raw_debug,
        merchant_token="2L8082NCG",
        starting_date="2024-01-01",
        end_date="2025-08-25",
    outdir="./charts"
)

    # Inspect what got rendered
    for req, res in summary.items():
        print("\n==", req, "==")
        for c in res["charts"]:
            print(f"- {c['metric']}: {c['path']}")
        if res["errors"]:
            print("Errors:", res["errors"])
