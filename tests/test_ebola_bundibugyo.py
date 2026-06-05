import csv
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

_PCODE_TO_NAME = {
    "CD5402ZS02": "Bunia",
    "CD5405ZS10": "Mongbalu",
    "CD1000ZS04": "Kinshasa",
    "CD6110ZS01": "Butembo",
    "CD9999ZS99": "",
}


def _stub_complete_admins(
    admins, countryiso3, provider_adm_names, adm_codes, adm_names, fuzzy_match=True
):
    """Minimal stand-in: fills adm_names from test pcode map, returns adm_level."""
    adm_level = len(adm_codes)
    for i in range(len(adm_codes) - 1, -1, -1):
        if adm_codes[i]:
            adm_names[i] = _PCODE_TO_NAME.get(adm_codes[i], adm_codes[i])
            return adm_level, []
        adm_level -= 1
    return 0, []


@contextmanager
def _patch_complete_admins():
    with patch(
        "hdx.scraper.ebola_bundibugyo.__main__.complete_admins",
        side_effect=_stub_complete_admins,
    ):
        yield


def _wide_row(
    admin3: str,
    pcode: str,
    date,
    cas_suspect=0,
    deces_suspect=0,
    cas_confirmes=0,
    deces_confirmes=0,
    cas_probable=None,
    contacts=None,
    gueris=0,
) -> dict:
    return {
        "Admin1": "Province",
        "Admin1Pcode": "CD10",
        "Admin2": "Territory",
        "Admin2Pcode": "CD1000",
        "Admin3": admin3,
        "Admin3Pcode": pcode if pcode is not None else "",
        "Admin3PcodeReview": pcode if pcode is not None else "",
        "CasSuspect": cas_suspect if cas_suspect is not None else "",
        "DecesSuspect": deces_suspect if deces_suspect is not None else "",
        "CasConfirmes": cas_confirmes if cas_confirmes is not None else "",
        "DecesConfirmes": deces_confirmes if deces_confirmes is not None else "",
        "CasProbable": cas_probable if cas_probable is not None else "",
        "Contacts": contacts if contacts is not None else "",
        "Gueris": gueris if gueris is not None else "",
        "Date": date if date is not None else "",
    }


def _make_mock_admins(pcode_map: dict[str, str]) -> list[MagicMock]:
    """Build a list of 3 mock AdminLevel objects sharing the same pcode_to_iso3 dict."""
    admins = []
    for _ in range(3):
        admin = MagicMock()
        admin.pcode_to_iso3 = pcode_map
        admins.append(admin)
    return admins


def _make_mock_spreadsheet(tabs: dict[str, list[dict]]) -> MagicMock:
    """Build a mock gspread Spreadsheet whose .worksheet(name).get_all_records() returns the given data."""
    mock_spreadsheet = MagicMock()

    worksheets = []
    for title in tabs:
        ws = MagicMock()
        ws.title = title
        worksheets.append(ws)
    mock_spreadsheet.worksheets.return_value = worksheets

    def worksheet_side_effect(name):
        ws = MagicMock()
        ws.get_all_records.return_value = tabs.get(name, [])
        return ws

    mock_spreadsheet.worksheet.side_effect = worksheet_side_effect
    return mock_spreadsheet


_META = ("2026-05-19", "2026-05-19")
_ADMINS = _make_mock_admins(
    {
        "CD5402ZS02": "COD",
        "CD5405ZS10": "COD",
        "CD1000ZS04": "COD",
        "CD6110ZS01": "COD",
    }
)


class TestNormaliseDate:
    def test_timestamp_string(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import normalise_date

        assert normalise_date("2026-03-15 00:00:00") == "2026-03-15"

    def test_iso_string(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import normalise_date

        assert normalise_date("2026-03-15") == "2026-03-15"

    def test_ambiguous_string(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import normalise_date

        assert normalise_date("January 10, 2026") == "2026-01-10"

    def test_none_returns_none(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import normalise_date

        assert normalise_date(None) is None
        assert normalise_date("") is None

    def test_unparseable_returns_none(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import normalise_date

        assert normalise_date("not a date") is None


class TestPrefixToIso3:
    def test_iso2_prefix(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import _prefix_to_iso3

        assert _prefix_to_iso3("CD5402ZS02") == "COD"

    def test_iso3_prefix(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import _prefix_to_iso3

        assert _prefix_to_iso3("COD001") == "COD"

    def test_no_prefix_returns_none(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import _prefix_to_iso3

        assert _prefix_to_iso3("123abc") is None


class TestTransformTab:
    def setup_method(self):
        self._patcher = _patch_complete_admins()
        self._patcher.__enter__()

    def teardown_method(self):
        self._patcher.__exit__(None, None, None)

    def test_basic_mapping(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import transform_tab

        records = [
            _wide_row(
                "Bunia",
                "CD5402ZS02",
                "2026-05-19",
                cas_suspect=90,
                deces_suspect=23,
                cas_confirmes=6,
                deces_confirmes=0,
                contacts=203,
                gueris=0,
            )
        ]
        result = transform_tab(records, *_META, _ADMINS)

        assert {r["location_country"] for r in result} == {"COD"}
        assert {r["location_level"] for r in result} == {3}
        assert {r["location_code_type"] for r in result} == {"pcode"}
        assert {r["reference_date"] for r in result} == {"2026-05-19"}
        assert {r["reporting_period_start"] for r in result} == {"2026-05-19"}
        assert {r["reporting_period_end"] for r in result} == {"2026-05-19"}
        assert {r["time_period"] for r in result} == {"cumulative"}
        assert {r["unit"] for r in result} == {"count"}
        assert {r["location_name"] for r in result} == {"Bunia"}
        assert {r["location_code"] for r in result} == {"CD5402ZS02"}

        measures = {(r["measure"], r["case_classification"]) for r in result}
        assert ("cases", "suspected") in measures
        assert ("deaths", "suspected") in measures
        assert ("cases", "confirmed") in measures
        assert ("deaths", "confirmed") in measures
        assert ("contacts", None) in measures
        assert ("cases", "recovered") in measures

        cas_suspect_row = [
            r
            for r in result
            if r["measure"] == "cases" and r["case_classification"] == "suspected"
        ]
        assert len(cas_suspect_row) == 1
        assert cas_suspect_row[0]["value"] == 90

        contacts_row = [r for r in result if r["measure"] == "contacts"]
        assert len(contacts_row) == 1
        assert contacts_row[0]["value"] == 203
        assert contacts_row[0]["case_classification"] is None

    def test_country_from_pcode_lookup(self):
        """location_country comes from AdminLevel.pcode_to_iso3 dict."""
        from hdx.scraper.ebola_bundibugyo.__main__ import transform_tab

        records = [_wide_row("Bunia", "CD5402ZS02", "2026-05-19", cas_suspect=10)]
        result = transform_tab(records, *_META, _ADMINS)
        assert {r["location_country"] for r in result} == {"COD"}

    def test_country_from_prefix_fallback(self):
        """If pcode not in admin lookup, falls back to prefix extraction."""
        from hdx.scraper.ebola_bundibugyo.__main__ import transform_tab

        records = [_wide_row("Unknown Zone", "CD9999ZS99", "2026-05-19", cas_suspect=5)]
        admins = _make_mock_admins({})  # empty lookup → prefix fallback
        result = transform_tab(records, *_META, admins)
        assert {r["location_country"] for r in result} == {"COD"}

    def test_row_date_used_as_reference_date(self):
        """reference_date comes from the row's Date field; period fields come from metadata."""
        from hdx.scraper.ebola_bundibugyo.__main__ import transform_tab

        records = [_wide_row("Bunia", "CD5402ZS02", "2026-05-19", cas_suspect=10)]
        result = transform_tab(records, "2026-05-24", "2026-05-27", _ADMINS)

        assert {r["reference_date"] for r in result} == {"2026-05-19"}
        assert {r["reporting_period_start"] for r in result} == {"2026-05-24"}
        assert {r["reporting_period_end"] for r in result} == {"2026-05-27"}

    def test_empty_date_string_rows_skipped(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import transform_tab

        records = [
            _wide_row("Bunia", "CD5402ZS02", "2026-05-19", cas_suspect=10),
            _wide_row("Kinshasa", "CD1000ZS01", None, cas_suspect=5),
        ]
        result = transform_tab(records, *_META, _ADMINS)
        assert {r["location_code"] for r in result} == {"CD5402ZS02"}

    def test_empty_pcode_string_rows_skipped(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import transform_tab

        records = [_wide_row("Unknown", None, "2026-05-19", cas_suspect=10)]
        result = transform_tab(records, *_META, _ADMINS)
        assert result == []

    def test_non_numeric_values_excluded(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import transform_tab

        records = [
            _wide_row(
                "Butembo",
                "CD6110ZS01",
                "2026-05-19",
                cas_suspect=1,
                cas_confirmes=1,
                contacts="ND",
            )
        ]
        result = transform_tab(records, *_META, _ADMINS)
        assert not any(r["measure"] == "contacts" for r in result)
        assert len(result) > 0

    def test_empty_measure_values_excluded(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import transform_tab

        records = [
            _wide_row(
                "Bunia", "CD5402ZS02", "2026-05-19", cas_suspect=10, cas_probable=None
            )
        ]
        result = transform_tab(records, *_META, _ADMINS)
        probable_rows = [
            r
            for r in result
            if r["measure"] == "cases" and r["case_classification"] == "probable"
        ]
        assert len(probable_rows) == 0

    def test_value_is_integer(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import transform_tab

        records = [_wide_row("Bunia", "CD5402ZS02", "2026-05-19", cas_suspect=90)]
        result = transform_tab(records, *_META, _ADMINS)
        assert all(isinstance(r["value"], int) for r in result)

    def test_empty_tab_returns_empty_list(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import transform_tab

        result = transform_tab([], *_META, _ADMINS)
        assert result == []


class TestMain:
    _fake_auth = json.dumps({"type": "service_account", "project_id": "test"})

    def _build_tabs(self) -> dict[str, list[dict]]:
        metadata = [
            {
                "tab_name": "260519",
                "reporting_period_start": "2026-05-19",
                "reporting_period_end": "2026-05-19",
            },
            {
                "tab_name": "260527",
                "reporting_period_start": "2026-05-24",
                "reporting_period_end": "2026-05-27",
            },
        ]
        tab519 = [
            _wide_row(
                "Bunia",
                "CD5402ZS02",
                "2026-05-19",
                cas_suspect=90,
                deces_suspect=23,
                cas_confirmes=6,
                deces_confirmes=0,
                contacts=203,
                gueris=0,
            ),
            _wide_row(
                "Bunia",
                "CD5402ZS02",
                "2026-05-20",
                cas_suspect=95,
                deces_suspect=25,
                cas_confirmes=7,
                deces_confirmes=0,
                contacts=210,
                gueris=0,
            ),
            _wide_row("Kinshasa", "CD1000ZS04", None, cas_suspect=0),
        ]
        tab527 = [
            _wide_row(
                "Bunia",
                "CD5402ZS02",
                "2026-05-27",
                cas_suspect=249,
                deces_suspect=48,
                cas_confirmes=37,
                deces_confirmes=0,
                contacts=404,
                gueris=0,
            ),
        ]
        return {"Metadata": metadata, "260519": tab519, "260527": tab527}

    def _run_main(self, tmp_path, tabs):
        from hdx.scraper.ebola_bundibugyo.__main__ import main

        output_csv = tmp_path / "output_data" / "combined_ebola_data.csv"
        mock_spreadsheet = _make_mock_spreadsheet(tabs)
        mock_config = MagicMock()
        mock_config.__getitem__ = MagicMock(return_value="https://example.com/sheet")
        mock_admins = _make_mock_admins({"CD5402ZS02": "COD", "CD1000ZS04": "COD"})

        with (
            patch(
                "hdx.scraper.ebola_bundibugyo.__main__.Configuration.read",
                return_value=mock_config,
            ),
            patch(
                "hdx.scraper.ebola_bundibugyo.__main__.gspread.service_account_from_dict",
                return_value=MagicMock(
                    open_by_url=MagicMock(return_value=mock_spreadsheet)
                ),
            ),
            patch(
                "hdx.scraper.ebola_bundibugyo.__main__._setup_admins",
                return_value=mock_admins,
            ),
            patch(
                "hdx.scraper.ebola_bundibugyo.__main__.complete_admins",
                side_effect=_stub_complete_admins,
            ),
            patch(
                "hdx.scraper.ebola_bundibugyo.__main__.OUTPUT_CSV",
                output_csv,
            ),
        ):
            main(gsheet_auth=self._fake_auth)

        return output_csv

    def _read_csv(self, path) -> list[dict]:
        with path.open() as f:
            return list(csv.DictReader(f))

    def test_main_produces_long_format_csv(self, configuration, tmp_path):
        output_csv = self._run_main(tmp_path, self._build_tabs())

        assert output_csv.exists()
        rows = self._read_csv(output_csv)

        assert {r["location_country"] for r in rows} == {"COD"}
        assert {r["location_level"] for r in rows} == {"3"}
        assert {r["location_code_type"] for r in rows} == {"pcode"}
        assert {r["time_period"] for r in rows} == {"cumulative"}
        assert {r["unit"] for r in rows} == {"count"}
        assert {r["reference_date"] for r in rows} == {
            "2026-05-19",
            "2026-05-20",
            "2026-05-27",
        }

    def test_main_metadata_dates_populated(self, configuration, tmp_path):
        output_csv = self._run_main(tmp_path, self._build_tabs())
        rows = self._read_csv(output_csv)

        rows_519 = [r for r in rows if r["reference_date"] == "2026-05-19"]
        assert {r["reporting_period_start"] for r in rows_519} == {"2026-05-19"}
        assert {r["reporting_period_end"] for r in rows_519} == {"2026-05-19"}

        rows_527 = [r for r in rows if r["reference_date"] == "2026-05-27"]
        assert {r["reporting_period_start"] for r in rows_527} == {"2026-05-24"}
        assert {r["reporting_period_end"] for r in rows_527} == {"2026-05-27"}

    def test_main_row_dates_preserved_across_dates_in_tab(
        self, configuration, tmp_path
    ):
        """Rows with different Date values in the same tab produce separate reference_date rows."""
        output_csv = self._run_main(tmp_path, self._build_tabs())
        rows = self._read_csv(output_csv)

        row_519 = [
            r
            for r in rows
            if r["location_code"] == "CD5402ZS02"
            and r["reference_date"] == "2026-05-19"
            and r["measure"] == "cases"
            and r["case_classification"] == "suspected"
        ]
        assert len(row_519) == 1
        assert int(row_519[0]["value"]) == 90

        row_520 = [
            r
            for r in rows
            if r["location_code"] == "CD5402ZS02"
            and r["reference_date"] == "2026-05-20"
            and r["measure"] == "cases"
            and r["case_classification"] == "suspected"
        ]
        assert len(row_520) == 1
        assert int(row_520[0]["value"]) == 95

    def test_main_no_duplicate_rows(self, configuration, tmp_path):
        output_csv = self._run_main(tmp_path, self._build_tabs())
        rows = self._read_csv(output_csv)

        keys = [
            (
                r["reference_date"],
                r["location_code"],
                r["measure"],
                r["case_classification"],
            )
            for r in rows
        ]
        assert len(keys) == len(set(keys))

    def test_main_output_columns(self, configuration, tmp_path):
        from hdx.scraper.ebola_bundibugyo.__main__ import OUTPUT_COLUMNS

        output_csv = self._run_main(tmp_path, self._build_tabs())
        with output_csv.open() as f:
            headers = next(csv.reader(f))
        assert headers == OUTPUT_COLUMNS
