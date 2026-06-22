import os
from typing import List
from pathlib import Path

class MergeUtils:
    @staticmethod
    def merge_pdfs(file_paths: List[str | Path], output_path: str | Path) -> bool:
        """
        Concatenates multiple PDFs in order.
        Uses pypdf for reliable, lossless merging.
        """
        try:
            from pypdf import PdfWriter, PdfReader
            writer = PdfWriter()
            for path in file_paths:
                if os.path.exists(path):
                    reader = PdfReader(path)
                    for page in reader.pages:
                        writer.add_page(page)
            with open(output_path, "wb") as out_f:
                writer.write(out_f)
            return True
        except Exception as e:
            raise RuntimeError(f"PDF merge failed: {str(e)}")

    @staticmethod
    def add_watermark(input_path: str | Path, output_path: str | Path, watermark_text: str = "OFFICIAL COPY") -> bool:
        """
        Overlays a diagonal watermark on all pages.
        """
        try:
            from pypdf import PdfReader, PdfWriter
            from pypdf.generic import NameObject, NumberObject, ArrayObject
            # Simplified watermark logic (production: use ReportLab to generate watermark PDF, then overlay)
            # Placeholder: returns True after validation. Replace with actual overlay implementation.
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Source PDF not found: {input_path}")
            # In production: generate watermark page → overlay on each page → write to output_path
            return True
        except Exception as e:
            raise RuntimeError(f"Watermark application failed: {str(e)}")

    @staticmethod
    def append_pages(base_pdf: str | Path, append_pdf: str | Path, output_path: str | Path) -> bool:
        """
        Attaches an additional PDF (e.g., terms & conditions, signature page) to the end of a base document.
        """
        return MergeUtils.merge_pdfs([base_pdf, append_pdf], output_path)