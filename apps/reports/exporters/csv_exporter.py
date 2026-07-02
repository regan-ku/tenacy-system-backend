import logging
import os
import csv
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

class CSVExporter:
    """
    Handles the generation of CSV files from structured tabular data.
    Lightweight and universally compatible with external accounting/CRM systems.
    """

    @staticmethod
    def generate_csv_from_list(data_list: list, filename: str, fieldnames: list) -> dict:
        try:
            save_path = os.path.join(settings.MEDIA_ROOT, 'reports', 'csvs')
            os.makedirs(save_path, exist_ok=True)
            full_path = os.path.join(save_path, filename)
            
            with open(full_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                writer.writeheader()
                for row in data_list:
                    # Filter row and ensure no nested dicts break the CSV writer
                    filtered_row = {}
                    for k in fieldnames:
                        val = row.get(k)
                        if isinstance(val, (dict, list)):
                            filtered_row[k] = str(val) # Convert complex types to string
                        else:
                            filtered_row[k] = val
                    writer.writerow(filtered_row)
            
            file_url = f"{settings.MEDIA_URL}reports/csvs/{filename}"
            
            logger.info(f"Successfully generated CSV: {filename}")
            return {
                "success": True,
                "file_url": file_url,
                "filename": filename,
                "generated_at": timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate CSV {filename}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "filename": filename
            }