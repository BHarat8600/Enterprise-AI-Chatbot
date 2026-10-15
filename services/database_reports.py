"""Direct database execution and full CSV reports; no LLM dependency."""

import csv
import json
import threading
import time
from pathlib import Path
from uuid import uuid4
from decimal import Decimal
import base64
import math

from fastapi.encoders import jsonable_encoder

from agents.database_agent import validate_read_only


class DatabaseReports:
    def __init__(self, root=Path("output/reports"), ttl=3600):
        self.root, self.ttl = Path(root), ttl
        self._reports = {}
        self._lock = threading.Lock()

    def _cleanup(self):
        now = time.time()
        with self._lock:
            for report_id, (_, path, created) in list(self._reports.items()):
                if now - created > self.ttl:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        # A Windows download may still hold the file open.
                        pass
                    del self._reports[report_id]

    def execute(self, tool, sql, session_id):
        validate_read_only(sql, tool)
        self._cleanup()
        self.root.mkdir(parents=True, exist_ok=True)
        report_id = str(uuid4())
        path = self.root / f"{report_id}.csv"
        preview, count = [], 0
        try:
            with (
                tool.query_cursor(sql) as cursor,
                path.open("w", newline="", encoding="utf-8-sig") as file,
            ):
                columns = [column[0] for column in cursor.description]
                if (
                    not columns
                    or not all(columns)
                    or len(columns) != len({c.lower() for c in columns})
                ):
                    raise ValueError("Result columns need unique, non-empty names; add SQL aliases")
                writer = csv.writer(file)
                writer.writerow(columns)
                while batch := cursor.fetchmany(1000):
                    for row in batch:
                        writer.writerow([self._csv_value(value) for value in row])
                        if len(preview) < 5:
                            preview.append(dict(zip(columns, row, strict=True)))
                    count += len(batch)
            response = jsonable_encoder(
                {
                    "rows": preview,
                    "columns": columns,
                    "row_count": count,
                    "column_count": len(columns),
                    "report_id": report_id,
                    "sql": sql,
                    "llm_calls": 0,
                    "total_tokens": 0,
                },
                custom_encoder={
                    Decimal: str,
                    bytes: lambda value: base64.b64encode(value).decode("ascii"),
                    memoryview: lambda value: base64.b64encode(value).decode("ascii"),
                    float: lambda value: value if math.isfinite(value) else str(value),
                },
            )
            with self._lock:
                self._reports[report_id] = (session_id, path, time.time())
            return response
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _csv_value(value):
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return value

    def get(self, report_id, session_id):
        self._cleanup()
        with self._lock:
            report = self._reports.get(report_id)
            if not report or report[0] != session_id or not report[1].is_file():
                return None
            return report[1]
