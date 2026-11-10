"""Synthetic GPT sources: measured quota, observed costs, validated account samples."""
__import__("os").environ["HYBRID_HANDS_ACCOUNT_LABEL_OFFLINE"] = "1"  # never read real account files
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hh_ps.codex import CodexData, _rate_limit_windows, _usage
from hh_ps.native_source import _read
from hh_ps.machine_usage import _gpt_usd
from hh_ps.render import _usage_json
from hh_ps.compact import usage_cells
from hh_ps.usage_enrichment import _five_hour, enrich_snapshot
from hh_ps.models import Usage
from hand_ext.codex_usage import price_for
from hand_ext.go_usage import estimate_cost

NOW = 1800000000

def iso(at):
    return dt.datetime.fromtimestamp(at, dt.timezone.utc).isoformat()

def event(at, pct=10, reset=NOW+1000, count=100, duration=10080):
    return {'timestamp': iso(at) if at is not None else None, 'type': 'event_msg',
            'payload': {'type': 'token_count', 'info': {'total_token_usage': {
                'input_tokens': count, 'cached_input_tokens': 0, 'output_tokens': count}},
                'rate_limits': {'primary': {'used_percent': pct,
                    'window_minutes': duration, 'resets_at': reset}}}}

def write(path, rows):
    path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')

class GptSourcesTest(unittest.TestCase):
    def test_a_measured_session_native_and_unknown_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp); root = home/'sessions'; root.mkdir()
            path = root/'rollout-child.jsonl'
            meta = {'type':'session_meta', 'payload':{'id':'child','parent_thread_id':'parent','model':'gpt-6.1-sol'}}
            source = CodexData(home, {}, {}, price_for({}))
            for first, last, expected in [(event(NOW-20),event(NOW-10,15),5),
                    (event(NOW-20),event(NOW-10),0),
                    (event(NOW-20),event(NOW-10,15,NOW+2000),None),
                    (event(NOW-20),event(NOW+1,15),None),
                    (event(NOW-20),event(None,15),None),
                    (event(NOW-20),event(NOW-10,101),None),
                    (event(NOW-20),event(NOW-10,9),None)]:
                with self.subTest(expected=expected,last=last):
                    write(path,[meta,first,last]); source._rollouts.clear()
                    usage=source.rollout_usage(str(path),NOW)
                    self.assertEqual(usage.week_pct,expected)
                    child=_read(path,NOW)[2]
                    self.assertEqual(child.usage.week_pct,expected)
                    if expected is not None:
                        self.assertEqual(_usage_json(usage)['week_pct_source'],'codex_rate_limits_delta')
                        self.assertFalse(usage.week_pct_estimated)
                        self.assertIn('riêng (đo)',str(usage_cells(usage)))
                        snapshot=SimpleNamespace(sessions=[SimpleNamespace(provider='codex',usage=usage,model='gpt-6.1-sol',subagents=[])],limits=[],iter_runs=lambda:[])
                        with patch('hh_ps.usage_enrichment._claude_five',return_value=None):
                            enrich_snapshot(snapshot,None,NOW)
                        self.assertEqual(snapshot.sessions[0].usage.week_pct,expected)
                    else:
                        self.assertNotIn('week_pct_source',_usage_json(usage))
            write(path,[meta,event(NOW-30),event(NOW-20,12,NOW+2000),event(NOW-10,15)])
            source._rollouts.clear()
            self.assertIsNone(source.rollout_usage(str(path),NOW).week_pct)
            legacy = [event(NOW-20), event(NOW-10,15)]
            for row in legacy:
                window = row['payload']['rate_limits'].pop('primary')
                window.pop('window_minutes')
                row['payload']['rate_limits']['secondary'] = window
            write(path,[meta]+legacy);source._rollouts.clear()
            legacy_usage=source.rollout_usage(str(path),NOW)
            self.assertEqual(legacy_usage.gpt_week_pct,15)
            self.assertIsNone(legacy_usage.week_pct)
            self.assertIsNone(_read(path,NOW)[2].usage.week_pct)

    def test_b_observed_machine_deltas_dedup_empty_and_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp); root=home/'sessions'; root.mkdir(); archive=home/'archived_sessions';archive.mkdir()
            meta={'type':'session_meta','payload':{'id':'thread','model':'gpt-6.1-sol','timestamp':iso(NOW-1000)}}
            rows=[meta,event(NOW-200,count=100),event(NOW-50,count=150)]
            write(root/'rollout-one.jsonl',rows);write(archive/'rollout-copy.jsonl',rows)
            write(root/'rollout-empty.jsonl',[{'type':'session_meta','payload':{'id':'empty','timestamp':iso(NOW-10)}}])
            source=SimpleNamespace(home=home)
            expected=estimate_cost({'input':50,'cached_input':0,'output':50},price_for({},'gpt-6.1-sol'))
            self.assertAlmostEqual(_gpt_usd(source,None,NOW-100,NOW),expected)
            rows[0]['payload']['model']='unknown-model'
            write(root/'rollout-one.jsonl',rows);write(archive/'rollout-copy.jsonl',rows)
            self.assertIsNone(_gpt_usd(source,None,NOW-100,NOW))
            self.assertIsNone(_gpt_usd(source,None,NOW-10,NOW))
            rows=[meta,event(NOW-50,count=150)]
            write(root/'rollout-one.jsonl',rows);write(archive/'rollout-copy.jsonl',rows)
            self.assertIsNone(_gpt_usd(source,None,NOW-100,NOW))

    def test_b2_store_cache_reuses_unchanged_and_follows_append(self):
        from hh_ps import machine_usage as mu
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp); root=home/'sessions'; root.mkdir(); source=SimpleNamespace(home=home)
            meta={'type':'session_meta','payload':{'id':'t','model':'gpt-6.1-sol','timestamp':iso(NOW-1000)}}
            rows=[meta,event(NOW-200,count=100),event(NOW-50,count=150)]; write(root/'rollout-a.jsonl',rows)
            first=_gpt_usd(source,None,NOW-100,NOW); _store_runtime._reset_for_tests()
            with patch.object(mu,'_records',side_effect=AssertionError('reloaded') if _store_runtime.enabled() else mu._records):
                self.assertEqual(_gpt_usd(source,None,NOW-100,NOW),first)
            write(root/'rollout-a.jsonl',rows+[event(NOW-10,count=400)])
            cached=_gpt_usd(source,None,NOW-100,NOW)
            with patch.dict(os.environ,{'HYBRID_HANDS_STORE':'off'}):
                self.assertEqual(cached,_gpt_usd(source,None,NOW-100,NOW))
            self.assertGreater(cached,first)

    def test_c_real_five_hour_samples_only(self):
        for duration,pct,at,reset,expected in [(300,12,NOW-10,NOW+1000,12),
                (10080,12,NOW-10,NOW+1000,None),(None,12,NOW-10,NOW+1000,12),
                (300,101,NOW-10,NOW+1000,None),(300,12,NOW+1,NOW+1000,None),
                (300,12,NOW-10,NOW-1,None),(300,12,0,NOW+1000,None),(300,True,NOW-10,NOW+1000,None),
                (300,float("nan"),NOW-10,NOW+1000,None),([],12,NOW-10,NOW+1000,None)]:
            with self.subTest(duration=duration,pct=pct,at=at,reset=reset):
                limits=event(NOW,duration=duration,pct=pct,reset=reset)['payload']['rate_limits']
                usage=_usage({},_rate_limit_windows(limits,at),None,NOW)
                self.assertEqual(usage.gpt_5h_pct,expected)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':tmp}):
            cache=Path(tmp)/'.statusline-cache.json'
            for reset,expected in [(iso(NOW+1000),23),(str(NOW+1000),23),(NOW-1,None),('bad',None)]:
                write(cache,[{'five':23,'five_reset':reset}]);os.utime(cache,(NOW-10,NOW-10))
                self.assertEqual(_five_hour('Claude',NOW),expected)
            cache.unlink()
            live=Path(tmp)/'.hh-claude-rate-limit.json'
            for stamp,pct,reset,expected in [(NOW-10,.31,iso(NOW+1000),31),(NOW+1,.31,NOW+1000,None),
                    (NOW-2000,.31,NOW+1000,None),(NOW-10,1.1,NOW+1000,None),(NOW-10,.31,NOW-1,None)]:
                write(live,[{'version':1,'windows':{'five_hour':{'ts':stamp,'utilization':pct,'resets_at':reset}}}])
                self.assertEqual(_five_hour('Claude',NOW),expected)
            live.unlink();self.assertIsNone(_five_hour('Claude',NOW))
            write(cache,[{'five':23,'five_reset':iso(NOW+1000)}]);os.utime(cache,(NOW-10,NOW-10))
            session=SimpleNamespace(provider='claude',usage=None,subagents=[],model='')
            snapshot=SimpleNamespace(sessions=[session],limits=[],iter_runs=lambda:[])
            enrich_snapshot(snapshot,None,NOW)
            self.assertEqual(session.usage.account_5h_pct,23)
            self.assertEqual(snapshot.limits[0].source,'claude_5h_cache')


# Store isolation: rollout readers must never write the real ~/.hybrid-hands/state.
import os as _os, shutil as _shutil, tempfile as _tempfile
from hh_store import runtime as _store_runtime
_STORE_PATCH = {}


def setUpModule():
    _STORE_PATCH["dir"] = _tempfile.mkdtemp()
    _STORE_PATCH["old"] = _os.environ.get("HYBRID_HANDS_STATE_DIR")
    _os.environ["HYBRID_HANDS_STATE_DIR"] = _STORE_PATCH["dir"]
    _store_runtime._reset_for_tests()


def tearDownModule():
    _store_runtime._reset_for_tests()
    if _STORE_PATCH["old"] is None:
        _os.environ.pop("HYBRID_HANDS_STATE_DIR", None)
    else:
        _os.environ["HYBRID_HANDS_STATE_DIR"] = _STORE_PATCH["old"]
    _shutil.rmtree(_STORE_PATCH["dir"], ignore_errors=True)


if __name__ == '__main__': unittest.main()
