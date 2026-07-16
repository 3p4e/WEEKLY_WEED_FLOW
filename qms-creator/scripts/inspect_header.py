from docx import Document
import sys

def inspect_header(path):
    doc = Document(path)
    print(f"Inspecting header of {path}")
    for section in doc.sections:
        header = section.header
        if header:
            print("Header found.")
            for i, table in enumerate(header.tables):
                print(f"  Header Table {i}: {len(table.rows)} rows x {len(table.columns)} columns")
                for r_idx, row in enumerate(table.rows):
                    row_text = [cell.text.strip() for cell in row.cells]
                    print(f"    Row {r_idx}: {row_text}")

if __name__ == "__main__":
    inspect_header("REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-01_General_Memorandum_v4_EDITED.docx")
