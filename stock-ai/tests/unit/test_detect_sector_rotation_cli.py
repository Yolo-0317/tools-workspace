from scripts.analysis import detect_sector_rotation as cli


class FailingProvider:
    warnings = ()

    def fetch_ranked_sectors(self, limit):
        raise RuntimeError("browser unavailable")


def test_ranking_failure_returns_nonzero_from_cli(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "build_provider", lambda: FailingProvider())

    assert cli.main(["--no-db", "--output", str(tmp_path / "report.md")]) == 2


def test_cli_rejects_out_of_range_limits() -> None:
    assert cli.main(["--no-db", "--top-sectors", "13"]) == 2
    assert cli.main(["--no-db", "--stocks-per-sector", "2"]) == 2
