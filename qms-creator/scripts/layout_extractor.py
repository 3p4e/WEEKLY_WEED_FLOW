#!/usr/bin/env python3
"""
Facility Layout Extractor
Extracts structured data from facility layout PDFs and SVGs.

Author: QMS Development Team
Date: 2025-01-22
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FacilityLayoutExtractor:
    """Extracts structured facility data from layout documents"""
    
    # Common room name patterns
    ROOM_PATTERNS = [
        r'R-?\d{3}',  # R-101, R101
        r'Room\s*\d+',
        r'Area\s*\d+',
        r'Zone\s*[A-Z]?\d*',
    ]
    
    # GMP classification patterns
    GMP_PATTERNS = {
        'GMP_A': r'Class\s*A|Grade\s*A|GMP[\s-]*A',
        'GMP_B': r'Class\s*B|Grade\s*B|GMP[\s-]*B',
        'GMP_C': r'Class\s*C|Grade\s*C|GMP[\s-]*C',
        'GMP_D': r'Class\s*D|Grade\s*D|GMP[\s-]*D',
        'GACP': r'GACP|Non[\s-]*GMP',
    }
    
    # HVAC patterns
    HVAC_PATTERNS = [
        r'AHU[\s-]*\d+',
        r'HVAC[\s-]*\d+',
        r'Air\s*Handler',
    ]
    
    def __init__(self, layout_dir: str):
        self.layout_dir = Path(layout_dir)
        self.facility_model: Dict[str, Any] = {
            "rooms": [],
            "hvac_systems": [],
            "water_systems": [],
            "zones": [],
            "source_files": []
        }
    
    def extract_all(self) -> Dict[str, Any]:
        """Extract data from all layout files in the directory"""
        if not self.layout_dir.exists():
            logger.error(f"Layout directory not found: {self.layout_dir}")
            return self.facility_model
        
        # Process PDFs
        for pdf_path in self.layout_dir.glob("*.pdf"):
            logger.info(f"Processing PDF: {pdf_path.name}")
            self._extract_from_pdf(pdf_path)
            self.facility_model["source_files"].append(str(pdf_path.name))
        
        # Process SVGs
        for svg_path in self.layout_dir.glob("*.svg"):
            logger.info(f"Processing SVG: {svg_path.name}")
            self._extract_from_svg(svg_path)
            self.facility_model["source_files"].append(str(svg_path.name))
        
        # Deduplicate
        self._deduplicate_rooms()
        
        return self.facility_model
    
    def _extract_from_pdf(self, pdf_path: Path):
        """Extract text and annotations from PDF"""
        if not PDF_AVAILABLE:
            logger.warning("pdfplumber not available, skipping PDF extraction")
            return
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    self._parse_text_for_rooms(text, pdf_path.name)
                    self._parse_text_for_hvac(text, pdf_path.name)
                    self._parse_text_for_zones(text, pdf_path.name)
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
    
    def _extract_from_svg(self, svg_path: Path):
        """Extract structured data from SVG layers"""
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
            
            # SVG namespace
            ns = {'svg': 'http://www.w3.org/2000/svg'}
            
            # Extract all text elements
            for text_elem in root.iter():
                if 'text' in text_elem.tag.lower() or text_elem.text:
                    text = text_elem.text or ""
                    if text.strip():
                        self._parse_text_for_rooms(text, svg_path.name)
                        self._parse_text_for_hvac(text, svg_path.name)
            
            # Look for layer groups (often contain semantic info)
            for group in root.findall('.//svg:g', ns):
                layer_name = group.get('{http://www.inkscape.org/namespaces/inkscape}label', '')
                if layer_name:
                    if 'room' in layer_name.lower():
                        logger.info(f"Found room layer: {layer_name}")
                    elif 'hvac' in layer_name.lower():
                        logger.info(f"Found HVAC layer: {layer_name}")
                        
        except Exception as e:
            logger.error(f"Error processing SVG {svg_path}: {e}")
    
    def _parse_text_for_rooms(self, text: str, source: str):
        """Parse text to find room identifiers"""
        for pattern in self.ROOM_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                room_id = match.upper().replace(' ', '-')
                
                # Determine GMP classification from context
                gmp_class = self._determine_gmp_class(text, match)
                
                room = {
                    "id": room_id,
                    "name": self._extract_room_name(text, match),
                    "area_type": gmp_class,
                    "source": source
                }
                
                if room not in self.facility_model["rooms"]:
                    self.facility_model["rooms"].append(room)
    
    def _parse_text_for_hvac(self, text: str, source: str):
        """Parse text to find HVAC system references"""
        for pattern in self.HVAC_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                hvac_id = match.upper().replace(' ', '-')
                
                hvac = {
                    "id": hvac_id,
                    "source": source
                }
                
                if hvac not in self.facility_model["hvac_systems"]:
                    self.facility_model["hvac_systems"].append(hvac)
    
    def _parse_text_for_zones(self, text: str, source: str):
        """Parse text to find zone information"""
        for gmp_class, pattern in self.GMP_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                zone = {
                    "classification": gmp_class,
                    "source": source
                }
                if zone not in self.facility_model["zones"]:
                    self.facility_model["zones"].append(zone)
    
    def _determine_gmp_class(self, text: str, room_match: str) -> str:
        """Determine GMP classification for a room based on surrounding text"""
        # Look in a window around the room match
        idx = text.find(room_match)
        window = text[max(0, idx-100):idx+100] if idx >= 0 else text
        
        for gmp_class, pattern in self.GMP_PATTERNS.items():
            if re.search(pattern, window, re.IGNORECASE):
                return gmp_class
        
        return "UNKNOWN"
    
    def _extract_room_name(self, text: str, room_id: str) -> str:
        """Extract full room name from context"""
        # Simple heuristic: look for text following the room ID
        idx = text.find(room_id)
        if idx >= 0:
            after = text[idx + len(room_id):idx + len(room_id) + 50]
            # Take first meaningful phrase
            match = re.match(r'[\s:–-]*([A-Za-z][A-Za-z\s]+)', after)
            if match:
                return match.group(1).strip()[:40]
        return room_id
    
    def _deduplicate_rooms(self):
        """Remove duplicate room entries"""
        seen = set()
        unique_rooms = []
        for room in self.facility_model["rooms"]:
            if room["id"] not in seen:
                seen.add(room["id"])
                unique_rooms.append(room)
        self.facility_model["rooms"] = unique_rooms
    
    def save_model(self, output_path: str):
        """Save the facility model to JSON"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.facility_model, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved facility model to {output_path}")


if __name__ == "__main__":
    import sys
    
    # Default paths
    layout_dir = "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/REFERENCE_MATERIALS/PP/Purely Plant InUse SOPs/Layout"
    output_path = "/home/azzu/PROJ/Cannabis EU GMP QMS Creator/data/facility_model.json"
    
    # Create output directory
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Run extraction
    extractor = FacilityLayoutExtractor(layout_dir)
    model = extractor.extract_all()
    extractor.save_model(output_path)
    
    # Print summary
    print(f"\n=== Facility Model Summary ===")
    print(f"Rooms found: {len(model['rooms'])}")
    print(f"HVAC systems: {len(model['hvac_systems'])}")
    print(f"Zones: {len(model['zones'])}")
    print(f"Source files: {len(model['source_files'])}")
