
import json
import os

def inspect_gaps():
    path = 'data/qms_master_analysis_report.json'
    if not os.path.exists(path):
        print(f"Report not found: {path}")
        return

    with open(path) as f:
        data = json.load(f)

    print("\n--- DOCUMENTS WITH REMAINING GAPS ---")
    
    # Handle both list and dict formats
    results = data if isinstance(data, list) else data.get('detailed_results', [])
    
    count = 0
    for item in results:
        # Only check .docx files as .txt templates are expected to have gaps or be ignored
        if item['sop_file'].endswith('.docx') and item.get('gaps'):
            print(f"\nFile: {item['sop_file']}")
            print(f"Gaps:")
            for gap in item['gaps']:
                print(f"  - {gap}")
            count += 1
            
    if count == 0:
        print("No .docx files with gaps found!")
    else:
        print(f"\nTotal .docx files with gaps: {count}")

if __name__ == "__main__":
    inspect_gaps()
