#!/usr/bin/env python3
"""
Comprehensive QMS Document Analysis
Analyzes all documents in the master QMS system and generates recommendations.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from collections import defaultdict

# Add project paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from sop_gap_analyzer import SOPGapAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_qms_documents(target_dir: str, checklist_path: str) -> Dict[str, Any]:
    """
    Analyze all QMS documents and generate a comprehensive report with recommendations.
    """
    analyzer = SOPGapAnalyzer(checklist_path)
    target_path = Path(target_dir)
    
    results = []
    stats = {
        "total": 0,
        "pass": 0,
        "conditional": 0,
        "needs_improvement": 0,
        "errors": 0
    }
    
    gap_frequency = defaultdict(int)
    strength_frequency = defaultdict(int)
    
    # Analyze all .docx files
    for sop_file in target_path.rglob("*.docx"):
        # Ignore venv and hidden directories
        parts = sop_file.parts
        if "venv" in parts or ".venv" in parts or any(p.startswith(".") for p in parts):
            continue
            
        logger.info(f"Analyzing: {sop_file.name}")
        result = analyzer.analyze_sop(str(sop_file))
        
        stats["total"] += 1
        
        if "error" in result:
            stats["errors"] += 1
        else:
            if result["verdict"] == "PASS":
                stats["pass"] += 1
            elif result["verdict"] == "CONDITIONAL PASS":
                stats["conditional"] += 1
            else:
                stats["needs_improvement"] += 1
            
            # Track frequency of gaps and strengths
            for gap in result.get("gaps", []):
                gap_frequency[gap] += 1
            for strength in result.get("strengths", []):
                strength_frequency[strength] += 1
        
        results.append(result)
    
    # Also analyze .txt files (templates)
    for txt_file in target_path.glob("**/*.txt"):
        logger.info(f"Analyzing template: {txt_file.name}")
        # Read content directly for txt files
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple analysis for txt files
            result = {
                "sop_file": txt_file.name,
                "file_type": "template",
                "content_length": len(content),
                "has_placeholders": "{{" in content or "{%" in content,
                "sections_detected": []
            }
            
            # Check for key sections
            section_keywords = ["PURPOSE", "SCOPE", "RESPONSIBILITY", "PROCEDURE", "REFERENCE", "REVISION"]
            for kw in section_keywords:
                if kw in content.upper():
                    result["sections_detected"].append(kw)
            
            results.append(result)
            stats["total"] += 1
            
        except Exception as e:
            logger.error(f"Error reading {txt_file}: {e}")
            stats["errors"] += 1
    
    # Generate recommendations
    recommendations = generate_recommendations(gap_frequency, stats)
    
    return {
        "statistics": stats,
        "top_gaps": sorted(gap_frequency.items(), key=lambda x: -x[1])[:10],
        "top_strengths": sorted(strength_frequency.items(), key=lambda x: -x[1])[:5],
        "recommendations": recommendations,
        "detailed_results": results
    }


def generate_recommendations(gap_frequency: Dict[str, int], stats: Dict[str, int]) -> List[Dict[str, str]]:
    """Generate actionable recommendations based on analysis results."""
    recommendations = []
    
    # Check for common gaps
    gap_list = list(gap_frequency.keys())
    
    # Header recommendations
    if any("Document Header" in g for g in gap_list):
        recommendations.append({
            "priority": "HIGH",
            "category": "Document Control",
            "issue": "Many documents missing standardized document header",
            "action": "Implement a consistent header template with SOP Number, Version, Effective Date, and Department across all documents.",
            "files_affected": gap_frequency.get("Missing section: Document Header", 0)
        })
    
    # Purpose/Scope recommendations
    if any("Purpose" in g for g in gap_list):
        recommendations.append({
            "priority": "HIGH",
            "category": "Content Structure",
            "issue": "Purpose sections missing or unclear",
            "action": "Add a clear 'Purpose' section at the beginning of each SOP stating the objective and why the procedure exists.",
            "files_affected": gap_frequency.get("Missing section: Purpose Section", 0)
        })
    
    if any("Scope" in g for g in gap_list):
        recommendations.append({
            "priority": "HIGH",
            "category": "Content Structure",
            "issue": "Scope sections missing",
            "action": "Define 'Scope' for each SOP specifying applicable areas, products, and any exclusions.",
            "files_affected": gap_frequency.get("Missing section: Scope Section", 0)
        })
    
    # Responsibilities
    if any("Responsibilities" in g for g in gap_list):
        recommendations.append({
            "priority": "MEDIUM",
            "category": "Accountability",
            "issue": "Responsibilities not clearly defined",
            "action": "Add a 'Responsibilities' table mapping roles to specific tasks within each SOP.",
            "files_affected": gap_frequency.get("Missing section: Responsibilities Section", 0)
        })
    
    # Definitions
    if any("Definitions" in g for g in gap_list):
        recommendations.append({
            "priority": "LOW",
            "category": "Clarity",
            "issue": "Technical terms not defined",
            "action": "Include a 'Definitions' section for SOPs with technical terminology or abbreviations.",
            "files_affected": gap_frequency.get("Missing section: Definitions Section", 0)
        })
    
    # GMP Compliance
    if any("GMP Compliance" in g for g in gap_list):
        recommendations.append({
            "priority": "HIGH",
            "category": "Regulatory",
            "issue": "GMP compliance language missing",
            "action": "Add explicit references to EU GMP (EudraLex Vol 4) and applicable Annexes in the References section.",
            "files_affected": gap_frequency.get("Quality check failed: GMP Compliance Language", 0)
        })
    
    # Deviation Handling
    if any("Deviation" in g for g in gap_list):
        recommendations.append({
            "priority": "MEDIUM",
            "category": "Quality",
            "issue": "Deviation handling not referenced",
            "action": "Include instructions for handling deviations and reference the master Deviation SOP.",
            "files_affected": gap_frequency.get("Quality check failed: Deviation Handling", 0)
        })
    
    # Overall quality recommendation
    if stats["needs_improvement"] > stats["pass"]:
        recommendations.append({
            "priority": "CRITICAL",
            "category": "System-Wide",
            "issue": f"{stats['needs_improvement']} documents need improvement vs {stats['pass']} passing",
            "action": "Consider a system-wide SOP review and standardization project using the provided standard checklist as a template.",
            "files_affected": stats["needs_improvement"]
        })
    
    return recommendations


if __name__ == "__main__":
    # Paths
    project_root = "/home/azzu/PROJ/Cannabis EU GMP QMS Creator"
    target_dir = os.path.join(project_root, "00_MASTER_DOCUMENTS")
    checklist_path = os.path.join(project_root, "CONTENT_CREATOR_FRAMEWORK", "sop_standard_checklist.yaml")
    output_path = os.path.join(project_root, "data", "qms_master_analysis_report.json")
    
    # Run analysis
    print("\n" + "="*60)
    print("QMS MASTER DOCUMENTS ANALYSIS")
    print("="*60 + "\n")
    
    report = analyze_qms_documents(target_dir, checklist_path)
    
    # Print summary
    stats = report["statistics"]
    print(f"\n📊 STATISTICS")
    print(f"   Total Documents: {stats['total']}")
    print(f"   ✅ Pass: {stats['pass']}")
    print(f"   ⚠️  Conditional: {stats['conditional']}")
    print(f"   ❌ Needs Improvement: {stats['needs_improvement']}")
    print(f"   🔴 Errors: {stats['errors']}")
    
    print(f"\n🔍 TOP GAPS (Most Frequent)")
    for gap, count in report["top_gaps"]:
        print(f"   • {gap}: {count} occurrences")
    
    print(f"\n💪 TOP STRENGTHS")
    for strength, count in report["top_strengths"]:
        print(f"   • {strength}: {count} documents")
    
    print(f"\n📋 RECOMMENDATIONS")
    for i, rec in enumerate(report["recommendations"], 1):
        print(f"\n   {i}. [{rec['priority']}] {rec['category']}")
        print(f"      Issue: {rec['issue']}")
        print(f"      Action: {rec['action']}")
        if rec.get('files_affected'):
            print(f"      Files Affected: {rec['files_affected']}")
    
    # Save full report
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Full report saved to: {output_path}")
