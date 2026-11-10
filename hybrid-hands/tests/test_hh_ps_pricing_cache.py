"""Only synthetic rollout/config/pricing sources are used here."""
__import__("os").environ["HYBRID_HANDS_ACCOUNT_LABEL_OFFLINE"] = "1"  # never read real account files
from test_hh_ps_gpt_nguon import NOW, event, iso, write
from pathlib import Path
from types import SimpleNamespace
import shared_config as config
import usage_pricing as pricing
from hh_ps.machine_usage import _gpt_usd


def test_many_threads_reuse_prices_and_config(tmp_path, monkeypatch):
    monkeypatch.setenv('HYBRID_HANDS_CONFIG', str(tmp_path / 'global.json'))
    monkeypatch.setenv('HYBRID_HANDS_PRICING_FILE', str(tmp_path / 'prices.json'))
    repo = tmp_path / 'repo.json'; repo.write_text('{}')
    prices = Path(pricing.DEFAULT_FILE).read_text(); (tmp_path / 'prices.json').write_text(prices)
    root = tmp_path / 'sessions'; root.mkdir()
    for i in range(20):
        write(root / f'rollout-{i}.jsonl', [{'type': 'session_meta', 'payload': {
            'id': str(i), 'timestamp': iso(NOW-90), 'model': 'gpt-6.1-sol'}},
            event(NOW-50, count=100), event(NOW-20, count=150)])
    cfg = SimpleNamespace(root=tmp_path, config_path=repo)
    config._load_config_cached.cache_clear(); pricing._load_prices_cached.cache_clear()
    values = [_gpt_usd(SimpleNamespace(home=tmp_path), cfg, NOW-100, NOW) for _ in range(2)]
    row = pricing.model_price('gpt-6.1-sol')
    assert values == [round(20 * 150 * (row['input'] + row['output']) / 1e6, 8)] * 2
    assert config._load_config_cached.cache_info().misses == pricing._load_prices_cached.cache_info().misses == 1
    result = config.load_config(known_root=tmp_path, config_file=repo)
    result.effective.clear(); pricing.load_prices().clear(); row.clear()
    assert config.load_config(known_root=tmp_path, config_file=repo).effective
    assert pricing.model_price('gpt-6.1-sol')
    repo.write_text('{"ext_hand":{"backends":{"codex":{"price_per_mtok":null}}}}')
    assert _gpt_usd(SimpleNamespace(home=tmp_path), cfg, NOW-100, NOW) is None
    (tmp_path / 'prices.json').write_text('{')
    assert pricing.load_prices() == {}
    assert config._load_config_cached.cache_info().misses == pricing._load_prices_cached.cache_info().misses == 2
