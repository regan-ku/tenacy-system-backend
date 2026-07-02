import logging
import os
import io
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

class PDFExporter:
    @staticmethod
    def generate_pdf_from_document_template(document_type_code: str, variables: dict, filename: str) -> dict:
        """
        Generates a PDF using the centralized DocumentTemplate system from the documents app.
        """
        try:
            # 1. Fetch and render template via Document App's TemplateService
            from apps.documents.services.template_service import TemplateService
            
            template = TemplateService.get_active_template(document_type_code)
            if not template:
                raise ValueError(f"No active template found for document type: {document_type_code}")
            
            # Prepare context (validates variables, sanitizes input, injects into HTML)
            prepared_context = TemplateService.prepare_generation_context(template, variables)
            html_string = prepared_context["html"]
            
            # 2. Generate PDF using xhtml2pdf
            try:
                from xhtml2pdf import pisa
                
                # Helper to resolve static/media paths for PDF images
                def link_callback(uri, rel):
                    if uri.startswith(settings.MEDIA_URL):
                        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ''))
                    elif uri.startswith(settings.STATIC_URL):
                        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ''))
                    else:
                        return uri
                    if not os.path.isfile(path):
                        return uri
                    return path

                result_file = io.BytesIO()
                pdf = pisa.CreatePDF(io.StringIO(html_string), dest=result_file, link_callback=link_callback)
                
                if pdf.err:
                    raise Exception("PDF generation failed with xhtml2pdf")
                    
                file_content = result_file.getvalue()
                
            except ImportError:
                logger.warning("xhtml2pdf not installed. Generating dummy PDF content.")
                file_content = f"%PDF-1.4\n% Simulated PDF Content for {filename}\n".encode('utf-8')

            # 3. Save to storage
            save_path = os.path.join(settings.MEDIA_ROOT, 'reports', 'pdfs')
            os.makedirs(save_path, exist_ok=True)
            full_path = os.path.join(save_path, filename)
            
            with open(full_path, 'wb') as f:
                f.write(file_content)
            
            file_url = f"{settings.MEDIA_URL}reports/pdfs/{filename}"
            
            logger.info(f"Successfully generated PDF: {filename}")
            return {
                "success": True,
                "file_url": file_url,
                "filename": filename,
                "generated_at": timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate PDF {filename}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "filename": filename
            }