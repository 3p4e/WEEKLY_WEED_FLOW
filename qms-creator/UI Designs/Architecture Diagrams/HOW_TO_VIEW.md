# How to View QMS Hierarchy Diagrams

## ✅ Quick Success: Updated Visualization System is Working!

The visualization system has been **successfully updated** and is now showing the correct status:

### 📊 Current Status (as of 2026-01-15)
- **Created Documents**: 39 (53.4%)
- **Planned Documents**: 34 (46.6%)
- **Total Documents**: 73 tracked
- **Families with Progress**: 13 document families

---

## 🎯 Option 1: View Interactive Dashboard (EASIEST)

Open the HTML dashboard in your browser:

```bash
# Open directly in browser
firefox docs/diagrams/index.html

# Or
google-chrome docs/diagrams/index.html

# Or on Mac
open docs/diagrams/index.html
```

**What you'll see:**
- Real-time statistics with pie chart
- Color-coded status cards
- Family-by-family progress bars
- Auto-refreshes every 5 minutes

---

## 🌐 Option 2: View Diagrams Online (NO INSTALLATION)

### Step 1: Go to PlantUML Online
Open your browser and go to:
**https://www.plantuml.com/plantuml/uml/**

### Step 2: Copy Diagram Content
Open one of these files in a text editor:
- `docs/diagrams/qms_hierarchy.puml` - Mind map of all documents
- `docs/diagrams/qms_family_status.puml` - Family progress cards
- `docs/diagrams/qms_document_status.puml` - Statistics overview
- `docs/diagrams/qms_structure.puml` - System architecture

### Step 3: Paste and View
1. Copy ALL the text from the .puml file
2. Paste it into the online editor (replacing any existing text)
3. Click "Submit" or press Enter
4. Diagram appears instantly!

---

## 📋 What Each Diagram Shows

### 1. **qms_hierarchy.puml** - Document Hierarchy Mind Map
```
✓ = Created & Published (Green)
○ = Planned (Purple)

Shows:
- All 13 document families as branches
- Individual documents with status symbols
- Annexes and sub-documents
- Hierarchical relationships
```

**Current Highlights:**
- QA_00 family: 18/22 documents created (82%)
- PRO_01 family: 3/3 documents created (100%)
- QC_01 family: 7/19 documents created (37%)

### 2. **qms_family_status.puml** - Family Overview Cards
```
Shows each family as a card with:
- Family name and description
- Progress bar
- Completion percentage
- Document count
```

### 3. **qms_document_status.puml** - Status Statistics
```
Shows:
- Overall statistics box
- Document count by status
- Color-coded legend
- Total completion metrics
```

### 4. **qms_structure.puml** - System Architecture
```
Shows:
- Document families as classes
- Document counts per family
- System organization
```

---

## 🔄 Update the Diagrams

To regenerate with latest document status:

```bash
python3 scripts/qms_hierarchy_visualizer.py
```

This will:
- Scan all directories for documents
- Update status detection
- Regenerate all diagrams
- Update the dashboard

---

## 📊 Current Progress Summary

### ✅ Completed Families (100%)
- **EQU_06**: Equipment Management (1/1)
- **PRO_01**: Cultivation Processes (3/3)
- **PRO_06**: Distribution & Logistics (1/1)
- **REC_09**: Records Management (1/1)
- **RES_10**: Research & Development (1/1)
- **SAN_07**: Sanitation & Hygiene (1/1)

### 🚧 In Progress Families
- **QA_00**: Quality System Core (18/22 - 82%)
- **PRO_03**: Production Operations (2/3 - 67%)
- **MAT_02**: Material Management (1/2 - 50%)
- **QC_01**: Batch Release (7/19 - 37%)
- **HRM_05**: Human Resources (2/6 - 33%)
- **QCS_01**: QC System (1/10 - 10%)

### 📋 Not Started
- **VAL_08**: Validation & Qualification (0/3)

---

## 🎨 Understanding the Colors

| Symbol | Status | Color | Meaning |
|--------|--------|-------|---------|
| ✓ | Created | 🟢 Green | Document exists and is ready |
| ✎ | Draft | 🟡 Peach | Under development |
| ◑ | In Progress | 🔴 Pink | Currently being worked on |
| ○ | Planned | 🟣 Lavender | Scheduled for creation |
| ✗ | Missing | ⚫ Gray | Not in scope |

---

## 💡 Quick Tips

1. **Best Viewer**: Use the HTML dashboard (`index.html`) for the best experience
2. **No Installation**: PlantUML online viewer requires nothing to install
3. **Auto-Updates**: Dashboard refreshes every 5 minutes automatically
4. **Mobile Friendly**: Dashboard works on phones and tablets
5. **Print Ready**: All diagrams can be exported as PNG/PDF from PlantUML

---

## 🐛 Troubleshooting

### Diagrams showing all as "Planned"?
Run the updated visualizer:
```bash
python3 scripts/qms_hierarchy_visualizer.py
```

### Can't see diagrams online?
1. Make sure you copy ALL text from the .puml file
2. Use Chrome or Firefox for best results
3. Try the alternative server: https://www.plantuml.com/plantuml/

### Dashboard not updating?
1. Clear browser cache (Ctrl+Shift+Delete)
2. Regenerate: `python3 scripts/qms_hierarchy_visualizer.py`
3. Refresh browser (F5)

---

## ✅ Success Confirmation

Your visualization system is now correctly showing:
- **39 created documents** (marked with ✓)
- **34 planned documents** (marked with ○)
- **53.4% overall completion**
- **All 13 families** properly tracked

The system is working perfectly and will continue to update as you create new documents!

---

## 📞 Need Help?

- Check the full guide: `docs/diagrams/README.md`
- Quick reference: `docs/diagrams/QUICK_REFERENCE.md`
- Run viewer helper: `python3 scripts/view_diagrams.py`
