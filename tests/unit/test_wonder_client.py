"""Unit tests for CDC WONDER response parsing — pure functions, no network."""

from __future__ import annotations

import pytest

from pulse.wonder_client import WonderClient


@pytest.fixture()
def client() -> WonderClient:
    return WonderClient()


def test_parse_rows_extracts_all_rows(client, sample_wonder_response_xml):
    rows = client.parse_rows(sample_wonder_response_xml)
    assert len(rows) == 3
    assert [r.is_total for r in rows] == [False, False, True]


def test_parse_rows_missing_data_table_raises(client):
    with pytest.raises(ValueError, match="data-table"):
        client.parse_rows("<page><response/></page>")


def test_get_headers_from_byvariables_and_measures(client, sample_wonder_response_xml):
    headers = client.get_headers(sample_wonder_response_xml)
    assert headers == ["Year", "Cases", "Rate per 100,000"]


def test_get_headers_falls_back_to_generic_columns(client):
    headers = client.get_headers("<page><response/></page>")
    assert headers == [f"Col {i + 1}" for i in range(6)]


def test_to_arrays_converts_numeric_cells(client, sample_wonder_response_xml):
    headers, data = client.to_arrays(sample_wonder_response_xml)
    assert headers == ["Year", "Cases", "Rate per 100,000"]
    assert data[0] == ["2020", 1234.0, 1.9]
    assert data[1] == ["2021", 1345.0, 2.1]
    # total row: label wins over the numeric dt for the first column
    assert data[2] == ["Total", 2579.0, 2.0]


def test_to_records_keys_by_header(client, sample_wonder_response_xml):
    records = client.to_records(sample_wonder_response_xml)
    assert records[0] == {"Year": "2020", "Cases": 1234.0, "Rate per 100,000": 1.9}
    assert len(records) == 3


def test_extract_dataset_id_from_xml(tmp_path):
    xml = (
        '<?xml version="1.0"?><request-parameters>'
        "<parameter><name>dataset_code</name><value>D202</value></parameter>"
        "</request-parameters>"
    )
    assert WonderClient._extract_dataset_id(xml) == "D202"


def test_extract_dataset_id_missing_returns_none():
    assert WonderClient._extract_dataset_id("<request-parameters/>") is None


def test_extract_dataset_id_malformed_xml_returns_none():
    assert WonderClient._extract_dataset_id("<not><valid") is None


def test_execute_file_reads_dataset_code_and_posts(tmp_path, monkeypatch):
    xml_path = tmp_path / "query.xml"
    xml_path.write_text(
        '<?xml version="1.0"?><request-parameters>'
        "<parameter><name>dataset_code</name><value>D202</value></parameter>"
        "</request-parameters>"
    )

    client = WonderClient()
    captured = {}

    def fake_query_from_xml(dataset_id, xml):
        captured["dataset_id"] = dataset_id
        captured["xml"] = xml
        return "<page>ok</page>"

    monkeypatch.setattr(client, "query_from_xml", fake_query_from_xml)
    result = client.execute_file(xml_path)

    assert result == "<page>ok</page>"
    assert captured["dataset_id"] == "D202"
    assert "D202" in captured["xml"]


def test_execute_file_no_dataset_code_raises(tmp_path):
    xml_path = tmp_path / "query.xml"
    xml_path.write_text("<request-parameters/>")
    with pytest.raises(ValueError, match="dataset_code"):
        WonderClient().execute_file(xml_path)
