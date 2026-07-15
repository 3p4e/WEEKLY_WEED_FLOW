"""
Vision OCR for Scanned PDFs

Falls back to GPT-4o vision API when PyPDF2 cannot extract text
from image-only / scanned PDF pages. Uses pdf2image to convert pages to images.

Supports GPT-4o (primary) and Gemini Flash (fallback).
"""

import base64
import io
import logging
import os
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

OCR_PROMPT = (
    "Extract all text from this document image. "
    "Return only the extracted text, preserving paragraphs and structure. "
    "Do not add commentary or descriptions."
)


class GeminiOCR:
    """OCR scanned PDF pages using GPT-4o vision, with Gemini Flash fallback."""

    def __init__(self, api_key: Optional[str] = None):
        # Prefer OpenAI, fall back to Gemini
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.gemini_key = api_key or os.getenv("GEMINI_API_KEY")
        self._backend = None

        if self.openai_key:
            self._backend = "openai"
        elif self.gemini_key:
            self._backend = "gemini"
        else:
            logger.warning("No OCR API key set (OPENAI_API_KEY or GEMINI_API_KEY) — OCR disabled")

    @property
    def available(self) -> bool:
        return self._backend is not None

    def ocr_pdf_pages(
        self,
        pdf_path: Path,
        page_indices: Optional[List[int]] = None,
        dpi: int = 200,
    ) -> List[str]:
        """
        OCR specific pages (or all) from a PDF file.

        Args:
            pdf_path: Path to the PDF file.
            page_indices: 0-based page indices to OCR. None = all pages.
            dpi: Resolution for PDF-to-image conversion.

        Returns:
            List of extracted text strings, one per page.
        """
        if not self.available:
            return []

        try:
            from pdf2image import convert_from_path
        except ImportError:
            logger.error("pdf2image not installed. Run: pip install pdf2image")
            return []

        # Convert PDF pages to images
        try:
            if page_indices is not None:
                first = min(page_indices) + 1
                last = max(page_indices) + 1
                all_images = convert_from_path(
                    str(pdf_path), dpi=dpi, first_page=first, last_page=last
                )
                # Map contiguous range back to only requested pages
                offset = min(page_indices)
                images_with_pages = []
                for idx in page_indices:
                    img_pos = idx - offset
                    if 0 <= img_pos < len(all_images):
                        images_with_pages.append((idx + 1, all_images[img_pos]))
            else:
                all_images = convert_from_path(str(pdf_path), dpi=dpi)
                images_with_pages = [(i + 1, img) for i, img in enumerate(all_images)]
        except Exception as e:
            logger.error(f"pdf2image conversion failed for {pdf_path.name}: {e}")
            return []

        logger.info(f"OCR via {self._backend} for {len(images_with_pages)} pages in {pdf_path.name}")

        results = []
        for page_num, img in images_with_pages:
            try:
                text = self._ocr_image(img)
                results.append(text)
                if text.strip():
                    logger.debug(f"OCR page {page_num}: {len(text)} chars")
                else:
                    logger.debug(f"OCR page {page_num}: no text found")
            except Exception as e:
                logger.warning(f"OCR failed for page {page_num} of {pdf_path.name}: {e}")
                results.append("")

        return results

    def _ocr_image(self, pil_image) -> str:
        """Route to the appropriate backend."""
        if self._backend == "openai":
            return self._ocr_openai(pil_image)
        else:
            return self._ocr_gemini(pil_image)

    def _ocr_openai(self, pil_image) -> str:
        """Send a PIL image to GPT-4o for OCR."""
        from openai import OpenAI

        # Encode image to base64 JPEG
        buf = io.BytesIO()
        pil_image.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        client = OpenAI(api_key=self.openai_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content.strip()

    def _ocr_gemini(self, pil_image) -> str:
        """Send a PIL image to Gemini Flash for OCR."""
        import google.generativeai as genai

        genai.configure(api_key=self.gemini_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content([OCR_PROMPT, pil_image])
        return response.text.strip() if response.text else ""
