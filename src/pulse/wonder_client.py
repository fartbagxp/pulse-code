"""CDC WONDER HTTP client and response parser."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests


@dataclass
class ResponseCell:
    label: Optional[str] = None
    value: Optional[str] = None
    data_total: Optional[str] = None

    def numeric(self) -> Optional[float]:
        raw = self.value or self.data_total
        if raw is None:
            return None
        try:
            return float(raw.replace(",", ""))
        except ValueError, AttributeError:
            return None


@dataclass
class ResponseRow:
    cells: list[ResponseCell]
    is_total: bool = False


class WonderClient:
    BASE_URL = "https://wonder.cdc.gov/controller/datarequest"

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout
        self.session = requests.Session()

    def query_from_xml(self, dataset_id: str, xml: str) -> str:
        data = {"request_xml": xml, "accept_datause_restrictions": "true"}
        resp = self.session.post(
            f"{self.BASE_URL}/{dataset_id}", data=data, timeout=self.timeout
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"CDC WONDER returned HTTP {resp.status_code}: {resp.text[:400]}"
            )
        return resp.text

    def execute_file(self, path: str | Path) -> str:
        xml = Path(path).read_text()
        dataset_id = self._extract_dataset_id(xml)
        if not dataset_id:
            raise ValueError(f"Could not find dataset_code in {path}")
        return self.query_from_xml(dataset_id, xml)

    @staticmethod
    def _extract_dataset_id(xml: str) -> Optional[str]:
        try:
            root = ET.fromstring(xml)
            el = root.find(".//parameter[name='dataset_code']/value")
            return el.text if el is not None else None
        except ET.ParseError:
            return None

    def parse_rows(self, xml: str) -> list[ResponseRow]:
        root = ET.fromstring(xml)
        table = root.find(".//data-table")
        if table is None:
            raise ValueError("No <data-table> found in CDC WONDER response")

        rows: list[ResponseRow] = []
        for r in table.findall("r"):
            cells = []
            is_total = False
            for c in r.findall("c"):
                dt = c.get("dt")
                if dt is not None:
                    is_total = True
                cells.append(
                    ResponseCell(label=c.get("l"), value=c.get("v"), data_total=dt)
                )
            rows.append(ResponseRow(cells=cells, is_total=is_total))
        return rows

    def get_headers(self, xml: str) -> list[str]:
        root = ET.fromstring(xml)
        var_labels: dict[str, str] = {}
        for var in root.findall(".//*[@code]"):
            code = var.get("code")
            label = var.get("label")
            if code and label:
                var_labels[code] = label
            for hier in var.findall("hier-level"):
                h_code = hier.get("code")
                h_label = hier.get("label")
                if h_code and h_label:
                    var_labels[h_code] = h_label

        headers: list[str] = []
        byvars = root.find(".//byvariables")
        if byvars is not None:
            for bv in byvars.findall("variable"):
                code = bv.get("code")
                headers.append(var_labels.get(code, code or ""))

        measure_labels: dict[str, str] = {}
        for m in root.findall(".//measure[@code]"):
            c = m.get("code")
            label = m.get("label")
            if c and label:
                measure_labels[c] = label

        ms = root.find(".//response//measure-selections")
        if ms is not None:
            for m in ms.findall("measure"):
                c = m.get("code")
                if c and not re.search(r"\.M\d{2,}$", c):
                    headers.append(measure_labels.get(c, c or ""))

        return headers or [f"Col {i + 1}" for i in range(6)]

    def to_records(self, xml: str) -> list[dict[str, Any]]:
        headers = self.get_headers(xml)
        rows = self.parse_rows(xml)
        records = []
        for row in rows:
            record: dict[str, Any] = {}
            for i, cell in enumerate(row.cells):
                key = headers[i] if i < len(headers) else f"col_{i}"
                if cell.label:
                    record[key] = cell.label
                else:
                    num = cell.numeric()
                    record[key] = (
                        num if num is not None else (cell.value or cell.data_total)
                    )
            if record:
                records.append(record)
        return records

    def to_arrays(self, xml: str) -> tuple[list[str], list[list[Any]]]:
        headers = self.get_headers(xml)
        rows = self.parse_rows(xml)
        data: list[list[Any]] = []
        for row in rows:
            r: list[Any] = []
            for cell in row.cells:
                if cell.label:
                    r.append(cell.label)
                else:
                    num = cell.numeric()
                    r.append(
                        num if num is not None else (cell.value or cell.data_total)
                    )
            data.append(r)
        return headers, data
