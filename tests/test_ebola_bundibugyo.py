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


class TestPipelineRun:
    _CONFIRMED_CASES = "nom,date,cumulative_confirmed_cases\nBunia,2026-05-19,6\nMongbalu,2026-05-19,13\n"
    _CONFIRMED_DEATHS = "nom,date,cumulative_confirmed_deaths\nBunia,2026-05-19,ND\nMongbalu,2026-05-19,2\n"
    _SUSPECTED_CASES = "nom,date,cumulative_suspected_cases\nBunia,2026-05-19,90\n"
    _SUSPECTED_DEATHS = "nom,date,cumulative_suspected_deaths\nBunia,2026-05-19,23\n"
    _CONTACTS = "nom,date,cumulative_contacts_traced\nBunia,2026-05-19,203\n"

    def _run_pipeline(self, configuration, tmp_path):
        from hdx.scraper.ebola_bundibugyo.pipeline import Pipeline

        fixtures = {
            "confirmed_cases": self._CONFIRMED_CASES,
            "confirmed_deaths": self._CONFIRMED_DEATHS,
            "suspected_cases": self._SUSPECTED_CASES,
            "suspected_deaths": self._SUSPECTED_DEATHS,
            "contacts": self._CONTACTS,
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
        assert all(r["source"] == "INRB-UMIE" for r in rows)

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
        assert {r["location_level"] for r in rows} == {3}
        assert {r["location_code"] for r in rows} == {""}
        assert {r["location_code_type"] for r in rows} == {"name"}


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
