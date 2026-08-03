from __future__ import annotations

from hermes_bilevel.cli import main
from hermes_bilevel.version import __version__


def test_cli_version(capsys):
    assert main(["version", "--json"]) == 0
    out = capsys.readouterr().out
    assert __version__ in out


def test_cli_doctor(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "init", "--json"]) == 0
    code = main(["--root", str(tmp_path), "doctor", "--json"])
    assert code in {0, 1}
