"""Unit tests for the NIS fixed-width SAS/DAT parser — pure functions, no network."""

from __future__ import annotations

from pulse.nis_parser import _extract, parse_sas_columns, stream_dat


def test_parse_sas_columns_pointer_notation():
    sas = """
    INPUT
      @1  SEQNUMC  7.
      @8  P_UTDMMX 1.
    ;
    """
    cols = parse_sas_columns(sas)
    assert cols["SEQNUMC"] == (0, 7)
    assert cols["P_UTDMMX"] == (7, 8)


def test_parse_sas_columns_strips_comments():
    sas = """
    /* block comment with @99 FAKE 1. inside */
    * statement comment with @98 FAKE2 1. ;
    INPUT
      @1  YEAR  4.
    ;
    """
    cols = parse_sas_columns(sas)
    assert cols == {"YEAR": (0, 4)}


def test_parse_sas_columns_no_input_block_returns_empty():
    assert parse_sas_columns("no input statement here") == {}


def test_parse_sas_columns_falls_back_to_range_notation():
    sas = "INPUT YEAR 8-11 ;"
    cols = parse_sas_columns(sas)
    assert cols["YEAR"] == (7, 11)


def test_extract_slices_line_by_column_positions():
    active = {"YEAR": (0, 4), "STATE": (4, 6)}
    row = _extract("2022CA", active)
    assert row == {"YEAR": "2022", "STATE": "CA"}


def test_extract_missing_trailing_columns_returns_empty_string():
    active = {"YEAR": (0, 4), "STATE": (4, 6)}
    row = _extract("2022", active)
    assert row == {"YEAR": "2022", "STATE": ""}


def test_stream_dat_yields_one_dict_per_line(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"2022CA\n2021TX\n"

    def fake_get(url, stream, timeout):
        return FakeResponse()

    monkeypatch.setattr("pulse.nis_parser.requests.get", fake_get)

    rows = list(stream_dat("http://example.com/fake.dat", {"YEAR": (0, 4), "STATE": (4, 6)}))
    assert rows == [{"YEAR": "2022", "STATE": "CA"}, {"YEAR": "2021", "STATE": "TX"}]
