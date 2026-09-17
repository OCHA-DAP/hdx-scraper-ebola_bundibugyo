import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

from hdx.utilities.compare import assert_files_same
from hdx.utilities.downloader import Download
from hdx.utilities.retriever import Retrieve


class TestNormaliseDate:
    def test_timestamp_string(self):
        from hdx.scraper.ebola_bundibugyo.pipeline import normalise_date

        assert normalise_date("2026-03-15 00:00:00") == "2026-03-15"

    def test_iso_string(self):
        from hdx.scraper.ebola_bundibugyo.pipeline import normalise_date

        assert normalise_date("2026-03-15") == "2026-03-15"

    def test_ambiguous_string(self):
        from hdx.scraper.ebola_bundibugyo.pipeline import normalise_date

        assert normalise_date("January 10, 2026") == "2026-01-10"

    def test_none_returns_none(self):
        from hdx.scraper.ebola_bundibugyo.pipeline import normalise_date

        assert normalise_date(None) is None
        assert normalise_date("") is None

    def test_unparseable_returns_none(self):
        from hdx.scraper.ebola_bundibugyo.pipeline import normalise_date

        assert normalise_date("not a date") is None


def _write_csv(tmp_path: Path, content: str, name: str = "test.csv") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestParseSourceCsv:
    def test_basic_confirmed_cases(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_source_csv

        p = _write_csv(
            tmp_path,
            "nom,date,cumulative_confirmed_cases\nBunia,2026-05-19,6\nMongbalu,2026-05-19,13\n",
        )
        rows = _parse_source_csv(
            p, "cases", "confirmed", "https://example.com/cases.csv"
        )
        assert len(rows) == 2
        bunia = next(r for r in rows if r["location_name"] == "Bunia")
        assert bunia["measure"] == "cases"
        assert bunia["case_classification"] == "confirmed"
        assert bunia["value"] == 6
        assert bunia["reference_date"] == "2026-05-19"
        assert bunia["location_country"] == "COD"
        assert bunia["location_level"] == 3
        assert bunia["location_code"] == ""
        assert bunia["location_code_type"] == "name"
        assert bunia["time_period"] == "cumulative"
        assert bunia["unit"] == "count"
        assert bunia["source"] == "INRB-UMIE"
        assert bunia["source_url"] == "https://example.com/cases.csv"

    def test_contacts_has_none_classification(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_source_csv

        p = _write_csv(
            tmp_path,
            "nom,date,cumulative_contacts_traced\nBunia,2026-05-19,203\n",
        )
        rows = _parse_source_csv(
            p, "contacts", None, "https://example.com/contacts.csv"
        )
        assert len(rows) == 1
        assert rows[0]["case_classification"] is None

    def test_nd_value_excluded(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_source_csv

        p = _write_csv(
            tmp_path,
            "nom,date,cumulative_confirmed_deaths\nBunia,2026-05-19,ND\nMongbalu,2026-05-19,5\n",
        )
        rows = _parse_source_csv(
            p, "deaths", "confirmed", "https://example.com/deaths.csv"
        )
        assert len(rows) == 1
        assert rows[0]["location_name"] == "Mongbalu"

    def test_empty_nom_row_skipped(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_source_csv

        p = _write_csv(
            tmp_path,
            "nom,date,cumulative_confirmed_cases\n,2026-05-19,6\nBunia,2026-05-19,6\n",
        )
        rows = _parse_source_csv(
            p, "cases", "confirmed", "https://example.com/cases.csv"
        )
        assert len(rows) == 1

    def test_empty_date_row_skipped(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_source_csv

        p = _write_csv(
            tmp_path,
            "nom,date,cumulative_confirmed_cases\nBunia,,6\nMongbalu,2026-05-19,13\n",
        )
        rows = _parse_source_csv(
            p, "cases", "confirmed", "https://example.com/cases.csv"
        )
        assert len(rows) == 1

    def test_value_is_int(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_source_csv

        p = _write_csv(
            tmp_path,
            "nom,date,cumulative_confirmed_cases\nBunia,2026-05-19,6\n",
        )
        rows = _parse_source_csv(
            p, "cases", "confirmed", "https://example.com/cases.csv"
        )
        assert isinstance(rows[0]["value"], int)

    def test_empty_csv_returns_empty_list(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_source_csv

        p = _write_csv(tmp_path, "nom,date,cumulative_confirmed_cases\n")
        rows = _parse_source_csv(
            p, "cases", "confirmed", "https://example.com/cases.csv"
        )
        assert rows == []

    def test_national_level(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_source_csv

        p = _write_csv(
            tmp_path,
            "nom,date,national_cumulative_confirmed_deaths\nDRC,2026-05-19,10\n",
        )
        rows = _parse_source_csv(
            p,
            "deaths",
            "confirmed",
            "https://example.com/national_deaths.csv",
            location_level=0,
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["location_level"] == 0
        assert row["location_name"] == "République démocratique du Congo"
        assert row["location_name_source"] == "DRC"
        assert row["location_code"] == "COD"
        assert row["location_code_type"] == "iso3"


class TestResolveLocation:
    def test_national_level(self):
        from hdx.scraper.ebola_bundibugyo.pipeline import _resolve_location

        code, code_type, name = _resolve_location("DRC", 0, None)
        assert code == "COD"
        assert code_type == "iso3"
        assert name == "République démocratique du Congo"

    def test_admin3_with_pcode(self):
        from hdx.scraper.ebola_bundibugyo.pipeline import _resolve_location

        admin3 = MagicMock()
        admin3.get_pcode.return_value = ("CD540205", None)
        admin3.pcode_to_name = {"CD540205": "Nyakunde"}
        code, code_type, name = _resolve_location("Nyakunde", 3, admin3)
        assert code == "CD540205"
        assert code_type == "pcode"
        assert name == "Nyakunde"

    def test_admin3_unresolved_pcode(self):
        from hdx.scraper.ebola_bundibugyo.pipeline import _resolve_location

        admin3 = MagicMock()
        admin3.get_pcode.return_value = (None, None)
        code, code_type, name = _resolve_location("Unknown Zone", 3, admin3)
        assert code == ""
        assert code_type == "name"
        assert name == "Unknown Zone"

    def test_no_admin3(self):
        from hdx.scraper.ebola_bundibugyo.pipeline import _resolve_location

        code, code_type, name = _resolve_location("Bunia", 3, None)
        assert code == ""
        assert code_type == "name"
        assert name == "Bunia"


class TestParseManualAdditions:
    def test_national_row(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_manual_additions

        p = _write_csv(
            tmp_path,
            "nom,date,measure,case_classification,location_level,value,source,notes\n"
            'DRC,2026-08-06,cases,confirmed,0,4120,"SitRep 083","Gap fill"\n',
        )
        rows = _parse_manual_additions(p, None)
        assert len(rows) == 1
        row = rows[0]
        assert row["reference_date"] == "2026-08-06"
        assert row["location_level"] == 0
        assert row["location_name"] == "République démocratique du Congo"
        assert row["location_code"] == "COD"
        assert row["location_code_type"] == "iso3"
        assert row["measure"] == "cases"
        assert row["case_classification"] == "confirmed"
        assert row["value"] == 4120
        assert row["time_period"] == "cumulative"
        assert row["unit"] == "count"
        assert row["source"] == "SitRep 083"
        assert row["notes"] == "Gap fill"
        assert row["data_quality_flag"] == "manual"

    def test_admin3_row_uses_admin3_lookup(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_manual_additions

        admin3 = MagicMock()
        admin3.get_pcode.return_value = ("CD540205", None)
        admin3.pcode_to_name = {"CD540205": "Nyakunde"}
        p = _write_csv(
            tmp_path,
            "nom,date,measure,case_classification,location_level,value,source,notes\n"
            'Nyakunde,2026-08-06,cases,confirmed,3,10,"SitRep 083","Gap fill"\n',
        )
        rows = _parse_manual_additions(p, admin3)
        assert len(rows) == 1
        assert rows[0]["location_code"] == "CD540205"
        assert rows[0]["location_name"] == "Nyakunde"

    def test_nd_value_excluded(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_manual_additions

        p = _write_csv(
            tmp_path,
            "nom,date,measure,case_classification,location_level,value,source,notes\n"
            'DRC,2026-08-06,cases,confirmed,0,ND,"SitRep 083","Gap fill"\n',
        )
        rows = _parse_manual_additions(p, None)
        assert rows == []

    def test_header_only_returns_empty_list(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_manual_additions

        p = _write_csv(
            tmp_path,
            "nom,date,measure,case_classification,location_level,value,source,notes\n",
        )
        rows = _parse_manual_additions(p, None)
        assert rows == []

    def test_contacts_has_none_classification(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_manual_additions

        p = _write_csv(
            tmp_path,
            "nom,date,measure,case_classification,location_level,value,source,notes\n"
            'DRC,2026-08-06,contacts,,0,10,"SitRep 083","Gap fill"\n',
        )
        rows = _parse_manual_additions(p, None)
        assert len(rows) == 1
        assert rows[0]["case_classification"] is None


class TestAmbiguousHealthZoneNames:
    """COD has two admin3 health zones both named "Lubunga": CD510102 in
    Tshopo (the outbreak location) and CD910703 in Kasai-Central. Without
    admin_name_mappings, AdminLevel's name lookup is ambiguous between them.
    """

    def _build_admin3(self):
        from hdx.location.adminlevel import AdminLevel

        admin_config = {
            "admin_name_mappings": {
                "COD|Lubunga": "CD510102",
                "COD|Lubunga (Tshopo)": "CD510102",
            }
        }
        admin3 = AdminLevel(admin_config=admin_config, admin_level=3)
        admin3.setup_from_iterable(
            [
                {
                    "Location": "COD",
                    "Admin Level": "3",
                    "P-Code": "CD510102",
                    "Name": "Lubunga",
                    "Parent P-Code": "CD5101",
                },
                {
                    "Location": "COD",
                    "Admin Level": "3",
                    "P-Code": "CD910703",
                    "Name": "Lubunga",
                    "Parent P-Code": "CD9107",
                },
            ],
            countryiso3s=["COD"],
        )
        return admin3

    def test_plain_name_resolves_to_tshopo_not_kasai_central(self):
        admin3 = self._build_admin3()
        pcode, _ = admin3.get_pcode("COD", "Lubunga")
        assert pcode == "CD510102"

    def test_suffixed_name_resolves_to_same_pcode(self):
        admin3 = self._build_admin3()
        pcode, _ = admin3.get_pcode("COD", "Lubunga (Tshopo)")
        assert pcode == "CD510102"

    def test_parse_source_csv_uses_mapped_pcode(self, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import _parse_source_csv

        admin3 = self._build_admin3()
        p = _write_csv(
            tmp_path,
            "nom,date,cumulative_confirmed_cases\n"
            "Lubunga (Tshopo),2026-07-10,1\n"
            "Lubunga,2026-07-19,1\n",
        )
        rows = _parse_source_csv(
            p, "cases", "confirmed", "https://example.com/cases.csv", admin3
        )
        assert {r["location_code"] for r in rows} == {"CD510102"}
        assert {r["location_name"] for r in rows} == {"Lubunga"}


class TestPipelineRun:
    _CONFIRMED_CASES = "nom,date,cumulative_confirmed_cases\nBunia,2026-05-19,6\nMongbalu,2026-05-19,13\n"
    _CONFIRMED_DEATHS = "nom,date,cumulative_confirmed_deaths\nBunia,2026-05-19,ND\nMongbalu,2026-05-19,2\n"
    _SUSPECTED_CASES = "nom,date,cumulative_suspected_cases\nBunia,2026-05-19,90\n"
    _SUSPECTED_DEATHS = "nom,date,cumulative_suspected_deaths\nBunia,2026-05-19,23\n"
    _CONTACTS = "nom,date,cumulative_contacts_traced\nBunia,2026-05-19,203\n"
    _NATIONAL_CONFIRMED_CASES = (
        "nom,date,national_cumulative_confirmed_cases\nDRC,2026-05-19,120\n"
    )
    _NATIONAL_CONFIRMED_DEATHS = (
        "nom,date,national_cumulative_confirmed_deaths\nDRC,2026-05-19,10\n"
    )
    _NATIONAL_SUSPECTED_CASES = (
        "nom,date,national_cumulative_suspected_cases\nDRC,2026-05-19,470\n"
    )
    _NATIONAL_SUSPECTED_DEATHS = (
        "nom,date,national_cumulative_suspected_deaths\nDRC,2026-05-19,95\n"
    )

    def _run_pipeline(self, configuration, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import Pipeline

        fixtures = {
            "confirmed_cases": self._CONFIRMED_CASES,
            "confirmed_deaths": self._CONFIRMED_DEATHS,
            "suspected_cases": self._SUSPECTED_CASES,
            "suspected_deaths": self._SUSPECTED_DEATHS,
            "contacts": self._CONTACTS,
            "national_confirmed_cases": self._NATIONAL_CONFIRMED_CASES,
            "national_confirmed_deaths": self._NATIONAL_CONFIRMED_DEATHS,
            "national_suspected_cases": self._NATIONAL_SUSPECTED_CASES,
            "national_suspected_deaths": self._NATIONAL_SUSPECTED_DEATHS,
        }
        csv_files = {}
        for key, content in fixtures.items():
            p = tmp_path / f"{key}.csv"
            p.write_text(content, encoding="utf-8")
            csv_files[key] = p

        mock_sources = {k: f"https://example.com/{k}.csv" for k in fixtures}

        def mock_download_file(url, **kwargs):
            key = next(k for k in csv_files if url.endswith(f"{k}.csv"))
            return csv_files[key]

        mock_admin3 = MagicMock()
        mock_admin3.get_pcode.return_value = (None, None)

        mock_retriever = MagicMock()
        mock_retriever.download_file.side_effect = mock_download_file

        with patch(
            "hdx.scraper.ebola_bundibugyo.pipeline.AdminLevel",
            return_value=mock_admin3,
        ):
            pipeline = Pipeline({"sources": mock_sources}, mock_retriever)
            return pipeline.run()

    def test_produces_rows(self, configuration, tmp_path):
        rows = self._run_pipeline(configuration, tmp_path)
        assert len(rows) > 0

    def test_all_metrics_present(self, configuration, tmp_path):
        rows = self._run_pipeline(configuration, tmp_path)
        pairs = {(r["measure"], r["case_classification"]) for r in rows}
        assert ("cases", "confirmed") in pairs
        assert ("deaths", "confirmed") in pairs
        assert ("cases", "suspected") in pairs
        assert ("deaths", "suspected") in pairs
        assert ("contacts", None) in pairs

    def test_source_populated(self, configuration, tmp_path):
        rows = self._run_pipeline(configuration, tmp_path)
        assert all(
            r["source"] == "INRB-UMIE"
            for r in rows
            if r.get("data_quality_flag") != "manual"
        )

    def test_no_duplicate_rows(self, configuration, tmp_path):
        rows = self._run_pipeline(configuration, tmp_path)
        keys = [
            (
                r["reference_date"],
                r["location_name"],
                r["measure"],
                r["case_classification"],
            )
            for r in rows
        ]
        assert len(keys) == len(set(keys))

    def test_nd_excluded(self, configuration, tmp_path):
        rows = self._run_pipeline(configuration, tmp_path)
        bunia_confirmed_deaths = [
            r
            for r in rows
            if r["location_name"] == "Bunia"
            and r["measure"] == "deaths"
            and r["case_classification"] == "confirmed"
        ]
        assert len(bunia_confirmed_deaths) == 0

    def test_location_fields(self, configuration, tmp_path):
        rows = self._run_pipeline(configuration, tmp_path)
        assert {r["location_country"] for r in rows} == {"COD"}
        assert {r["location_level"] for r in rows} == {0, 3}

        subnational = [r for r in rows if r["location_level"] == 3]
        assert {r["location_code"] for r in subnational} == {""}
        assert {r["location_code_type"] for r in subnational} == {"name"}

        national = [r for r in rows if r["location_level"] == 0]
        assert {r["location_code"] for r in national} == {"COD"}
        assert {r["location_code_type"] for r in national} == {"iso3"}
        assert {r["location_name"] for r in national} == {
            "République démocratique du Congo"
        }

    def test_manual_addition_fills_gap(self, configuration, tmp_path):
        manual_csv = tmp_path / "manual_additions.csv"
        manual_csv.write_text(
            "nom,date,measure,case_classification,location_level,value,source,notes\n"
            'DRC,2026-08-06,cases,confirmed,0,4120,"SitRep 083","Gap fill"\n',
            encoding="utf-8",
        )
        with patch(
            "hdx.scraper.ebola_bundibugyo.pipeline.script_dir_plus_file",
            return_value=str(manual_csv),
        ):
            rows = self._run_pipeline(configuration, tmp_path)

        matches = [r for r in rows if r["reference_date"] == "2026-08-06"]
        assert len(matches) == 1
        assert matches[0]["value"] == 4120
        assert matches[0]["data_quality_flag"] == "manual"

    def test_manual_addition_overrides_downloaded_row(self, configuration, tmp_path):
        manual_csv = tmp_path / "manual_additions.csv"
        manual_csv.write_text(
            "nom,date,measure,case_classification,location_level,value,source,notes\n"
            'DRC,2026-05-19,cases,confirmed,0,999,"Correction","Overrides downloaded"\n',
            encoding="utf-8",
        )
        with patch(
            "hdx.scraper.ebola_bundibugyo.pipeline.script_dir_plus_file",
            return_value=str(manual_csv),
        ):
            rows = self._run_pipeline(configuration, tmp_path)

        matches = [
            r
            for r in rows
            if r["reference_date"] == "2026-05-19"
            and r["measure"] == "cases"
            and r["case_classification"] == "confirmed"
            and r["location_level"] == 0
        ]
        assert len(matches) == 1
        assert matches[0]["value"] == 999
        assert matches[0]["data_quality_flag"] == "manual"


class TestPipeline:
    def test_output_fixture(self, configuration, fixtures_dir, input_dir, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import OUTPUT_COLUMNS, Pipeline

        with Download(user_agent="test") as downloader:
            retriever = Retrieve(
                downloader=downloader,
                fallback_dir=tmp_path,
                saved_dir=input_dir,
                temp_dir=tmp_path,
                save=False,
                use_saved=True,
            )
            pipeline = Pipeline(configuration, retriever)
            rows = pipeline.run()

        output_path = tmp_path / "combined_ebola_data.csv"
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, restval="")
            writer.writeheader()
            writer.writerows(
                {
                    col: ("" if row.get(col) is None else row.get(col))
                    for col in OUTPUT_COLUMNS
                }
                for row in rows
            )

        assert_files_same(fixtures_dir / "combined_ebola_data.csv", output_path)


class TestGenerateDataset:
    _ROWS = [
        {
            "reference_date": "2026-05-19",
            "location_name": "Bunia",
            "measure": "cases",
            "case_classification": "confirmed",
            "value": 6,
        },
        {
            "reference_date": "2026-05-14",
            "location_name": "Mongbalu",
            "measure": "deaths",
            "case_classification": "suspected",
            "value": 57,
        },
    ]

    def test_dataset_metadata(self, configuration, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import (
            _DATASET_NAME,
            _DATASET_TITLE,
            _MAINTAINER,
            _OWNER_ORG,
            _TAGS,
            Pipeline,
        )

        mock_retriever = MagicMock()
        pipeline = Pipeline(configuration, mock_retriever)

        with patch("hdx.scraper.ebola_bundibugyo.pipeline.Dataset") as MockDataset:
            mock_ds = MagicMock()
            MockDataset.return_value = mock_ds
            pipeline.generate_dataset(str(tmp_path), self._ROWS)

        MockDataset.assert_called_once_with(
            {"name": _DATASET_NAME, "title": _DATASET_TITLE}
        )
        mock_ds.add_country_location.assert_called_once_with("COD")
        mock_ds.set_maintainer.assert_called_once_with(_MAINTAINER)
        mock_ds.set_organization.assert_called_once_with(_OWNER_ORG)
        mock_ds.set_expected_update_frequency.assert_called_once_with("Every day")
        mock_ds.set_subnational.assert_called_once_with(True)
        mock_ds.add_tags.assert_called_once_with(_TAGS)

    def test_time_period_from_rows(self, configuration, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import Pipeline

        mock_retriever = MagicMock()
        pipeline = Pipeline(configuration, mock_retriever)

        with patch("hdx.scraper.ebola_bundibugyo.pipeline.Dataset") as MockDataset:
            mock_ds = MagicMock()
            MockDataset.return_value = mock_ds
            pipeline.generate_dataset(str(tmp_path), self._ROWS)

        mock_ds.set_time_period.assert_called_once_with("2026-05-14", "2026-05-19")

    def test_resource_generated(self, configuration, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import OUTPUT_COLUMNS, Pipeline

        mock_retriever = MagicMock()
        pipeline = Pipeline(configuration, mock_retriever)

        with patch("hdx.scraper.ebola_bundibugyo.pipeline.Dataset") as MockDataset:
            mock_ds = MagicMock()
            MockDataset.return_value = mock_ds
            pipeline.generate_dataset(str(tmp_path), self._ROWS)

        args, kwargs = mock_ds.generate_resource.call_args
        assert args[1] == "drc_ebola_cases_consolidated.csv"
        assert args[2] == self._ROWS
        assert kwargs["headers"] == OUTPUT_COLUMNS

    def test_returns_dataset(self, configuration, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import Pipeline

        mock_retriever = MagicMock()
        pipeline = Pipeline(configuration, mock_retriever)

        with patch("hdx.scraper.ebola_bundibugyo.pipeline.Dataset") as MockDataset:
            mock_ds = MagicMock()
            MockDataset.return_value = mock_ds
            result = pipeline.generate_dataset(str(tmp_path), self._ROWS)

        assert result is mock_ds
