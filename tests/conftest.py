"""Shared fixtures for the pulse test suite."""

from __future__ import annotations

import pytest

SAMPLE_WONDER_RESPONSE_XML = """\
<?xml version="1.0"?>
<page>
  <response>
    <byvariables>
      <variable code="D202.V20" />
    </byvariables>
    <measure-selections>
      <measure code="D202.M1" />
      <measure code="D202.M3" />
    </measure-selections>
  </response>
  <measure code="D202.M1" label="Cases" />
  <measure code="D202.M3" label="Rate per 100,000" />
  <parameter code="D202.V20" label="Year" />
  <data-table>
    <r>
      <c l="2020" />
      <c v="1234" />
      <c v="1.9" />
    </r>
    <r>
      <c l="2021" />
      <c v="1345" />
      <c v="2.1" />
    </r>
    <r>
      <c l="Total" dt="2579" />
      <c dt="2579" />
      <c dt="2.0" />
    </r>
  </data-table>
</page>
"""


@pytest.fixture()
def sample_wonder_response_xml() -> str:
    return SAMPLE_WONDER_RESPONSE_XML
