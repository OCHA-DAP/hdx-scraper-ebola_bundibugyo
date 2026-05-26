import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


class TestParseFrenchDate:
    def test_standard_format(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import parse_french_date

        result = parse_french_date(
            "Nombre de cas et de décès liés à Ebola désagrégés au niveau "
            "administratif 3 à la date du 24 mai 2026"
        )
        assert result == "2026-05-24"

    def test_all_months(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import parse_french_date

        cases = [
            ("à la date du 1 janvier 2026", "2026-01-01"),
            ("à la date du 15 février 2026", "2026-02-15"),
            ("à la date du 3 mars 2026", "2026-03-03"),
            ("à la date du 10 avril 2025", "2025-04-10"),
            ("à la date du 24 mai 2026", "2026-05-24"),
            ("à la date du 7 juin 2026", "2026-06-07"),
            ("à la date du 20 juillet 2025", "2025-07-20"),
            ("à la date du 31 août 2025", "2025-08-31"),
            ("à la date du 12 septembre 2025", "2025-09-12"),
            ("à la date du 5 octobre 2025", "2025-10-05"),
            ("à la date du 11 novembre 2025", "2025-11-11"),
            ("à la date du 25 décembre 2025", "2025-12-25"),
        ]
        for description, expected in cases:
            assert parse_french_date(description) == expected

    def test_no_date_returns_none(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import parse_french_date

        assert parse_french_date("No date here") is None
        assert parse_french_date("") is None

    def test_unknown_month_returns_none(self):
        from hdx.scraper.ebola_bundibugyo.__main__ import parse_french_date

        assert parse_french_date("à la date du 24 xyz 2026") is None


class TestMain:
    def _make_xlsx(self, tmp_path: str, name: str, rows: list[dict]) -> str:
        path = Path(tmp_path) / name
        pd.DataFrame(rows).to_excel(path, sheet_name="Data", index=False)
        return str(path)

    def test_main_combines_resources(self, configuration):
        from hdx.scraper.ebola_bundibugyo.__main__ import main

        rows1 = [{"Zone": "A", "Cases": 10}]
        rows2 = [{"Zone": "B", "Cases": 5}]

        with tempfile.TemporaryDirectory() as tmp_dir:
            xlsx1 = self._make_xlsx(tmp_dir, "resource1.xlsx", rows1)
            xlsx2 = self._make_xlsx(tmp_dir, "resource2.xlsx", rows2)

            resource1 = MagicMock()
            resource1.get_file_type.return_value = "xlsx"
            resource1.get.return_value = "Données à la date du 10 janvier 2026"
            resource1.__getitem__ = MagicMock(return_value="resource1.xlsx")
            resource1.download.return_value = ("url1", xlsx1)

            resource2 = MagicMock()
            resource2.get_file_type.return_value = "xlsx"
            resource2.get.return_value = "Données à la date du 15 mars 2026"
            resource2.__getitem__ = MagicMock(return_value="resource2.xlsx")
            resource2.download.return_value = ("url2", xlsx2)

            mock_dataset = MagicMock()
            mock_dataset.get_resources.return_value = [resource1, resource2]

            output_dir = Path(tmp_dir) / "saved_data"

            with (
                patch(
                    "hdx.scraper.ebola_bundibugyo.__main__.Dataset.read_from_hdx",
                    return_value=mock_dataset,
                ),
                patch(
                    "hdx.scraper.ebola_bundibugyo.__main__.OUTPUT_CSV",
                    output_dir / "combined_ebola_data.csv",
                ),
                patch("tempfile.TemporaryDirectory") as mock_tmpdir,
            ):
                mock_tmpdir.return_value.__enter__ = MagicMock(return_value=tmp_dir)
                mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
                main()

            assert (output_dir / "combined_ebola_data.csv").exists()
            df = pd.read_csv(output_dir / "combined_ebola_data.csv")
            assert "AsOf" in df.columns
            assert len(df) == 2
            assert set(df["AsOf"]) == {"2026-01-10", "2026-03-15"}

    def test_main_skips_non_xlsx(self, configuration):
        from hdx.scraper.ebola_bundibugyo.__main__ import main

        csv_resource = MagicMock()
        csv_resource.get_file_type.return_value = "csv"

        mock_dataset = MagicMock()
        mock_dataset.get_resources.return_value = [csv_resource]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "saved_data"

            with (
                patch(
                    "hdx.scraper.ebola_bundibugyo.__main__.Dataset.read_from_hdx",
                    return_value=mock_dataset,
                ),
                patch(
                    "hdx.scraper.ebola_bundibugyo.__main__.OUTPUT_CSV",
                    output_dir / "combined_ebola_data.csv",
                ),
            ):
                main()

            assert not (output_dir / "combined_ebola_data.csv").exists()
            csv_resource.download.assert_not_called()

    @pytest.mark.parametrize(
        "description,expected_as_of",
        [
            (
                "Nombre de cas et de décès liés à Ebola désagrégés au niveau "
                "administratif 3 à la date du 24 mai 2026",
                "2026-05-24",
            ),
            ("No date here", None),
        ],
    )
    def test_parse_date_variants(self, description, expected_as_of):
        from hdx.scraper.ebola_bundibugyo.__main__ import parse_french_date

        assert parse_french_date(description) == expected_as_of
