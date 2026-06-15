import json
import logging

import gspread
from hdx.api.configuration import Configuration

from .pipeline import OUTPUT_COLUMNS

logger = logging.getLogger(__name__)


def write_to_gsheet(
    rows: list[dict], gsheet_auth: str, configuration: Configuration
) -> None:
    info = json.loads(gsheet_auth)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    gc = gspread.service_account_from_dict(info, scopes=scopes)
    spreadsheet_url = configuration["output_gsheet"]
    tab_id = int(configuration["output_gsheet_tab_id"])
    logger.info(f"Opening output Google Sheet: {spreadsheet_url}")
    spreadsheet = gc.open_by_url(spreadsheet_url)
    worksheet = spreadsheet.get_worksheet_by_id(tab_id)
    data = [
        [("" if row.get(col) is None else str(row.get(col))) for col in OUTPUT_COLUMNS]
        for row in rows
    ]
    worksheet.clear()
    worksheet.update("A1", [OUTPUT_COLUMNS] + data)
    logger.info(f"Written {len(rows)} rows to Google Sheet tab id {tab_id}")
