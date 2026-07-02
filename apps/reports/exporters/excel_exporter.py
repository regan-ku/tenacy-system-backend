import logging
import os
from django.conf import settings
from django.utils import timezone

# In production, ensure you have: pip install openpyxl
import openpyxl

logger = logging.getLogger(__name__)

class ExcelExporter:
    """
    Handles the generation of Excel (.xlsx) workbooks from structured data.
    Ideal for tabular reports requiring further manipulation by the user.
    """

    @staticmethod
    def generate_excel_from_data(data, filename: str, sheet_name: str = "Report Data") -> dict:
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet_name

            # ✅ DYNAMIC HANDLING: Check if data is Tabular (List of Dicts) or Summary (Single Dict)
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                # TABULAR DATA (e.g., Landlord Statements, Portfolio Metrics)
                headers = list(data[0].keys())
                ws.append([h.replace("_", " ").title() for h in headers])
                
                for row in data:
                    ws.append([row.get(k) for k in headers])
                    
            elif isinstance(data, dict):
                # SUMMARY DATA (e.g., Occupancy Summary, Financial KPIs)
                ws.append(["Report Generated At", data.get("generated_at", timezone.now().isoformat())])
                ws.append(["Period", data.get("period_days", "N/A")])
                ws.append([]) # Empty row for spacing

                # Flatten nested dicts so Excel doesn't break
                def flatten_dict(d, parent_key='', sep='_'):
                    items = []
                    for k, v in d.items():
                        new_key = f"{parent_key}{sep}{k}" if parent_key else k
                        if isinstance(v, dict):
                            items.extend(flatten_dict(v, new_key, sep=sep).items())
                        else:
                            items.append((new_key, v))
                    return dict(items)

                flat_data = flatten_dict(data)
                ws.append(["Metric", "Value"])
                for key, value in flat_data.items():
                    ws.append([key.replace("_", " ").title(), value])

            # Auto-adjust column widths for readability
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