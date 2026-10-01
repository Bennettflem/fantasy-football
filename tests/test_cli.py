"""Every subcommand should run end to end against the synthetic league and print something."""
import pytest

from ffstats import __main__ as cli

COMMANDS = [
    ["power-rankings", "--season", "2101"],
    ["playoff-odds", "--season", "2101", "--sims", "100"],
    ["playoff-odds", "--season", "2101", "--sims", "50", "--json"],
    ["what-if", "--season", "2101"],
    ["what-if", "--season", "2100", "--json"],
    ["spreads", "--season", "2101"],
    ["spreads", "--season", "2101", "--week", "1"],
    ["roast", "--season", "2101"],
    ["roast", "--season", "2101", "--json"],
    ["rivalry", "--season", "2101"],
    ["rivalry", "Ann", "Ben"],
    ["rivalry", "Ann", "Ben", "--json"],
    ["trade-finder", "--season", "2101"],
    ["trade-finder", "--season", "2101", "--top", "2"],
    ["draft-grades"],
    ["draft-grades", "--season", "2100"],
    ["draft-grades", "--json"],
    ["league-stats"],
]


@pytest.mark.parametrize("argv", COMMANDS, ids=lambda a: " ".join(a))
def test_command_runs(argv, seasons, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_all", lambda *a, **k: seasons)
    cli.main(argv)
    assert capsys.readouterr().out.strip()


def test_rivalry_rejects_one_name(seasons, monkeypatch):
    monkeypatch.setattr(cli, "load_all", lambda *a, **k: seasons)
    with pytest.raises(SystemExit):
        cli.main(["rivalry", "Ann"])
