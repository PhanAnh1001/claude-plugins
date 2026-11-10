"""Three-tier model commands use only public temporary configuration fixtures."""
import json
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"
sys.path.insert(0, str(LIB))
from hand_ext.cli import main


def fixture(tmp_path, monkeypatch):
    global_file = tmp_path / "global.json"
    global_file.write_text(json.dumps({"main_session": {"codex_effort": "medium"},
        "ext_hand": {"backends": {"claude-main": {"effort": "high"}}}}))
    monkeypatch.setenv("HYBRID_HANDS_CONFIG", str(global_file))
    repo = tmp_path / "repo"
    repo.mkdir()
    path = repo / ".claude/hybrid-hands.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"side_session": {"codex_effort": "xhigh"},
        "ext_hand": {"backends": {"codex": {"home": "fake-home"}},
                     "claude_accounts": {"v1": {"config_dir": "fake-dir", "max_day_pct": 5}}}}))
    return repo, path


def test_view(tmp_path, monkeypatch, capsys):
    repo, path = fixture(tmp_path, monkeypatch)
    original = path.read_bytes()
    assert main(["models", "--cwd", str(repo), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["brain"]["codex_effort"]["source"] == "global"
    assert data["side"]["codex_effort"]["source"] == "repo"
    assert data["brain"]["provider"]["source"] == "plugin"
    assert data["hand"]["backends"]["claude-v1"]["effort"]["source"] == "global"
    assert "fake-home" not in json.dumps(data) and path.read_bytes() == original
    assert main(["models", "options", "--cwd", str(repo), "--json"]) == 0
    options = json.loads(capsys.readouterr().out)
    assert [row["value"] for row in options["tiers"]] == ["brain", "side", "hand"]
    assert "claude-sonnet-5-5" in options["providers"]["claude"]["models"]
    assert [row["value"] for row in options["hand_backends"] if row["in_order"]] == data["hand"]["order"]["value"]
    assert set(options["presets"]) == {"brain", "side", "hand_claude", "hand_other"}
    assert all(rows[0]["args"] == [] and len(rows) <= 4 for rows in options["presets"].values())
    assert path.read_bytes() == original


def test_set_and_validation(tmp_path, monkeypatch, capsys):
    repo, path = fixture(tmp_path, monkeypatch)
    prefix = ["models", "set", "--cwd", str(repo), "--json"]
    original = path.read_bytes()
    valid = ["--brain", "claude:claude-sonnet-5-5:high@v2", "--hand", "claude-main=claude-opus-5-5:medium"]
    assert main(prefix + valid + ["--dry-run"]) == 0
    diff = json.loads(capsys.readouterr().out)["diff"]
    assert diff["main_session.claude_model"] == [None, "claude-sonnet-5-5"]
    assert diff["ext_hand.backends.claude-v1.effort"] == [None, "medium"]
    assert path.read_bytes() == original
    assert main(prefix + ["--brain", "claude-sonnet-5-5:high", "--side", "gpt-6.1-sol:max",
                          "--hand", "claude-v2=claude-haiku-5-5:low", "--dry-run"]) == 0
    diff = json.loads(capsys.readouterr().out)["diff"]
    assert diff["main_session.claude_model"][1] == "claude-sonnet-5-5"
    assert diff["side_session.codex_effort"][1] == "xhigh"
    assert diff["ext_hand.backends.claude-v2.model"][1] == "claude-haiku-5-5"
    for invalid in ("codex:missing:low", "codex:gpt-6.1-sol:invalid", "claude:claude-opus-5-5:high@v99"):
        assert main(prefix + ["--brain", invalid]) == 2
        assert path.read_bytes() == original
    capsys.readouterr()
    for flags, key, value in (
        (["--tier", "side", "--model", "gpt-6.1-sol", "--effort", "max"],
         "side_session.codex_effort", "xhigh"),
        (["--tier", "hand", "--model", "claude-haiku-5-5", "--effort", "low", "--account", "v2"],
         "ext_hand.backends.claude-v2.model", "claude-haiku-5-5"),
    ):
        assert main(prefix + flags + ["--dry-run"]) == 0
        assert json.loads(capsys.readouterr().out)["diff"][key][1] == value
    assert main(prefix + ["--tier", "brain"] + valid + ["--dry-run"]) == 2
    assert path.read_bytes() == original
    assert main(prefix + valid) == 0
    data = json.loads(path.read_text())
    assert data["ext_hand"]["backends"]["codex"]["home"] == "fake-home"
    assert data["ext_hand"]["backends"]["claude-v1"]["effort"] == "medium"
    assert "codex_effort" not in data["main_session"]
    assert main(prefix + valid) == 0
    capsys.readouterr()


def test_unset_hand(tmp_path, monkeypatch, capsys):
    repo, path = fixture(tmp_path, monkeypatch)
    raw = json.loads(path.read_text())
    ext = raw["ext_hand"]
    ext["order"] = ["codex"]
    ext["backends"]["codex"].update(model="bad", effort="bad")
    ext["claude_accounts"]["v1"].update(model="bad", effort="bad")
    ext["backends"]["claude-main"] = {"model": "bad", "effort": "bad", "max_day_pct": 5}
    path.write_text(json.dumps(raw))
    assert main(["models", "unset", "hand", "--cwd", str(repo), "--json", "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["diff"]["ext_hand.backends.codex.model"] == ["bad", None]
    assert json.loads(path.read_text()) == raw
    assert main(["models", "unset", "hand", "--cwd", str(repo), "--json"]) == 0
    ext = json.loads(path.read_text())["ext_hand"]
    assert "order" not in ext
    assert ext["backends"]["codex"] == {"home": "fake-home"}
    assert ext["backends"]["claude-main"] == {"max_day_pct": 5}
    assert ext["claude_accounts"]["v1"] == {"config_dir": "fake-dir", "max_day_pct": 5}
    data = json.loads(capsys.readouterr().out)
    assert data["hand"]["backends"]["claude-v1"]["effort"]["source"] == "global"
