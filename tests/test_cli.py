"""Tests for brood.cli -- the command-line surface."""
import pytest

from brood.cli import main


def test_primes(capsys):
    assert main(["primes", "30"]) == 0
    assert capsys.readouterr().out.strip() == "2 3 5 7 11 13 17 19 23 29"


def test_factor(capsys):
    assert main(["factor", "60"]) == 0
    assert capsys.readouterr().out.strip() == "60 = 2 * 2 * 3 * 5"


def test_hamming_count(capsys):
    assert main(["hamming", "10"]) == 0
    assert capsys.readouterr().out.strip() == "1 2 3 4 5 6 8 9 10 12"


def test_hamming_up_to(capsys):
    assert main(["hamming", "--up-to", "12"]) == 0
    assert capsys.readouterr().out.strip() == "1 2 3 4 5 6 8 9 10 12"


def test_wheel_default(capsys):
    assert main(["wheel"]) == 0
    out = capsys.readouterr().out
    assert "circumference=30" in out
    assert "1 7 11 13 17 19 23 29" in out


def test_wheel_up_to(capsys):
    assert main(["wheel", "--up-to", "31"]) == 0
    assert capsys.readouterr().out.strip() == "1 7 11 13 17 19 23 29 31"


def test_table_mod(capsys):
    assert main(["table", "4", "--mod", "5"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0].split() == ["1", "2", "3", "4"]


def test_requires_subcommand():
    with pytest.raises(SystemExit):
        main([])
