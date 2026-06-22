import logging
import os
from django.conf import settings
from django.utils import timezone

# In production, install: pip install openpyxl
import openpyxl
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

class ExcelExporter:
    """
    Handles the generation of Excel (.xlsx) workbooks from structured data.
    Ideal for tabular reports requiring further manipulation by the user.
    """

    @staticmethod
    def generate_excel_from_data(data: dict, filename: str, sheet_name: str = "Report Data") -> dict:
        """
        Creates an Excel workbook and populates it with the provided snapshot data.
        """
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet_name

            # 1. Add Metadata Header
            ws.append(["Report Generated At", data.get("generated_at", timezone.now().isoformat())])
            ws.append(["Period", data.get("period_days", "N/A")])
            ws.append([""]) # Empty row for spacing

            # 2. Dynamically add data based on keys (Simplified for structure)
            # In a full implementation, this would iterate through specific tabular keys 
            # like data.get('upcoming_expiries') or data.get('application_trend')
            
            headers = ["Metric", "Value"]
            ws.append(headers)
            
            # Example: Extracting summary metrics
            summary = data.get("occupancy_summary", {})
            for key, value in summary.items():
                ws.append([key.replace("_", " ").title(), value])

            # Auto-adjust column widths
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                ws.column_dimensions[column].width = adjusted_width

            # 3. Save to storage
            save_path = os.path.join(settings.MEDIA_ROOT, 'reports', 'excels')
            os.makedirs(save_path, exist_ok=True)
            full_path = os.path.join(save_path, filename)
            
            wb.save(full_path)
            file_url = f"{settings.MEDIA_URL}reports/excels/{filename}"
            
            logger.info(f"Successfully generated Excel: {filename}")
            return {
                "success": True,
                "file_url": file_url,
                "filename": filename,
                "generated_at": timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate Excel {filename}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "filename": filename
            }