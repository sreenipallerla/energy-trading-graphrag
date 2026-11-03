import os

from etg.envfile import load_env


def test_loads_values_and_ignores_comments(tmp_path, monkeypatch):
    for k in ("A_ONE", "B_TWO", "C_THREE", "D_FOUR"):
        monkeypatch.delenv(k, raising=False)
    f = tmp_path / ".env"
    f.write_text("# comment\n\nA_ONE=1\nexport B_TWO = \"two words\"\nC_THREE='x=y'\nbadline\nD_FOUR=\n")
    names = load_env(f)
    assert os.environ["A_ONE"] == "1" and os.environ["B_TWO"] == "two words"
    assert os.environ["C_THREE"] == "x=y" and os.environ["D_FOUR"] == ""
    assert set(names) == {"A_ONE", "B_TWO", "C_THREE", "D_FOUR"}
    for k in ("A_ONE", "B_TWO", "C_THREE", "D_FOUR"):
        monkeypatch.delenv(k)


def test_existing_environment_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("E_FIVE", "from-shell")
    f = tmp_path / ".env"
    f.write_text("E_FIVE=from-file\n")
    assert load_env(f) == [] and os.environ["E_FIVE"] == "from-shell"


def test_missing_file_is_fine(tmp_path):
    assert load_env(tmp_path / "nope.env") == []
