## Tóm tắt
- Merge main: xong, merge commit `35f8371` trên `side/cfg-goi-a`, hai parent `9d4b23b` và `e077e8a`; không rebase/force/push/merge vào main.
- Xung đột `lib/hand_ext/cli.py`, `config.py`: giữ lệnh managed/provider/run --mode của main và loader chung/config --json/account/path của Gói A.
- `lib/hand_ext/constants.py`, `lib/shared_config.py`: mode=shell/paseo={} là defaults canonical, paseo bắt buộc object; global → repo deep merge và nguồn từng key.
- `tests/test_shared_config.py`, `test_hand_paseo_controller.py`: bổ sung kiểm cấu hình Paseo trong 3 ca hiện có và sửa fixture mock private helper đã cũ.
- Kiểm chứng merge: Sol chạy 21 module (11 Gói A + 10 Paseo) → 109 tests PASS/17.818s; diff/cached check PASS.
- Full suite sau merge: hand riêng chỉ chạy đúng một lần trên commit cuối `35f8371` → 490 tests PASS/76.744s, exit 0; không sửa code sau đó.
- Gói A gốc `9d4b23b` được giữ: shared loader, side_session/hh_ps adapters, usage_pricing explicit overrides; thông tin trước merge ở các mục lịch sử bên dưới.
- Worktree sạch. Chưa kiểm runtime/daemon Paseo thật hoặc cập nhật plugin; version/changelog/release ngoài phần được import từ main vẫn dành cho Opus.
- Đã giữ mọi report/log/marker trong output/llm; tín hiệu lần này là `cfg-goi-a-merge.done`, tạo sau khi ghi bàn giao.

## Merge main

Theo yêu cầu tiếp của Opus sau khi chấp nhận Gói A, Sol chạy `git merge --no-commit --no-ff main` trong worktree hiện tại. Không rebase, không force; chỉ commit trên `side/cfg-goi-a`.

- Merge commit: `35f8371add3087dca5d9787b76272d7d0744cf11`.
- Parent 1: `9d4b23bf9ec988286adfc68d86b8abb1f6263ecc` (Gói A đã được chấp nhận).
- Parent 2: `e077e8a40223e92dc23b6a7624898ac77f9b6da4` (main, managed Paseo transport opt-in).
- Subject: `Merge main into side/cfg-goi-a: preserve Paseo transport and shared config`.
- `git status --short` sau toàn bộ kiểm chứng: rỗng. Không push, không merge vào main, không cập nhật runtime thật.

### Giải xung đột và review

1. `lib/hand_ext/cli.py`: giữ cả parser `config --json`/GlobalConfigError handler và các parser/handler `provider`, `managed`, `run --mode`, execution key từ main.
2. `lib/hand_ext/config.py`: giữ loader chung, nguồn cấu hình, account alias, isolation và resolve backend path từ Gói A; giữ `ExtConfig.mode`/`paseo` và validation của main; resolve `paseo.package_root`/`state_root` tương đối từ repo. Target giữ schema transport của main.
3. `lib/hand_ext/constants.py`: thêm canonical DEFAULTS `mode: shell`, `paseo: {}` để shared loader và `config --json` có đầy đủ giá trị/nguồn plugin.
4. `lib/shared_config.py`: thêm `ext_hand.paseo` vào section bắt buộc object. Global sai kiểu báo path và khác 0; nested Paseo dict vẫn deep merge global → repo, CLI --mode thắng.
5. `tests/test_shared_config.py`: chỉ mở rộng 3 test method hiện có để kiểm default/source, global/repo mode+paseo, relative paths, CLI --mode bằng mock và global paseo sai kiểu; không thêm test method mới.
6. `tests/test_hand_paseo_controller.py`: fixture từ main còn mock `_read_section` (không còn dùng trong adapter mới); bỏ mock vô hiệu ở setup và đổi mock kiểm mode sai sang kết quả shared loader. Không đổi mục tiêu/điều kiện assertion.

`hh_ps/registry_source.py` tự merge sạch: giữ shared loader của A và projection/dedup managed executions của main. Các thay đổi main khác được giữ nguyên; tài liệu/version/changelog từ main được import theo merge, Sol không tự sửa chúng. So với main, `hand_ext/run_cmd.py` không có diff; logic gắn cha PASEO_AGENT_ID/CODEX_THREAD_ID giữ nguyên. Rà soát các JSON reader trong lib: chỉ shared loader đọc `hybrid-hands.json`; reader package/metadata/state/ledger/pricing canonical không phải reader cấu hình repo.

### Test hẹp sau giải conflict

Hand sửa conflict ban đầu chạy 109 tests, có 1 fail do mock cũ trong fixture Paseo; sau sửa fixture test riêng PASS. Sol review và chạy lại đầy đủ 21 module dưới, HOME/HYBRID_HANDS_CONFIG/HYBRID_HANDS_STATE_DIR/CLAUDE_HOME tạm, Go live tắt:

```sh
PYTHONPATH=hybrid-hands/tests python3 -m unittest \
  test_shared_config test_hand_ext_parallel test_hand_ext_codex test_hand_ext_usage \
  test_hh_ps_codex test_hh_ps_gpt_nguon test_hh_ps_limits \
  test_hand_ext_config_worktree test_hand_ext_defaults test_side_session test_hh_ps_multirepo \
  test_hand_paseo_admission test_hand_paseo_cli test_hand_paseo_completion \
  test_hand_paseo_controller test_hand_paseo_execution test_hand_paseo_gateway \
  test_hand_paseo_integration test_hand_paseo_provider test_hand_paseo_transport test_hh_ps_paseo_hand
```

- Kết quả cuối: `Ran 109 tests in 17.818s`, `OK`, exit 0.
- Log: `/Users/anhtp/app/claude-plugins-wt/cfg-goi-a/output/llm/cfg-goi-a/merge-narrow.log`.
- `git diff --check`, `git diff --cached --check`: PASS; không còn unmerged path/marker trước commit.
- Sau review/test hẹp, Sol stage và commit merge `35f8371`, rồi mới giao một hand khác chỉ chạy full suite trên commit đó.

### Full suite trên commit cuối — hand riêng, đúng một lượt

```sh
python3 -m unittest discover -s hybrid-hands/tests -p 'test_*.py'
```

- Expected/actual HEAD: `35f8371add3087dca5d9787b76272d7d0744cf11`; hand kiểm HEAD + worktree sạch trước khi chạy.
- Kết quả: **490 tests PASS**, `Ran 490 tests in 76.744s`, `OK`, exit **0**. Thời gian subprocess tổng: 77.536s.
- Không chạy lại suite, không sửa tracked file, không thêm test/code; commit sau full vẫn là commit đã kiểm chứng.
- Cô lập HOME: `output/llm/cfg-goi-a/merge-full-home-nxqzb8lr`; env config trỏ absent-global.json trong HOME tạm, state/CLAUDE_HOME cũng tạm, Go live tắt.
- Log: `/Users/anhtp/app/claude-plugins-wt/cfg-goi-a/output/llm/cfg-goi-a/merge-full-suite.log`.
- Result có commit/exit/elapsed/home: `/Users/anhtp/app/claude-plugins-wt/cfg-goi-a/output/llm/cfg-goi-a/merge-full-suite.result`.
- Marker độc quyền `output/llm/cfg-goi-a/merge-full-suite.started` được giữ để ngăn lặp. Đây là một lượt mới được Opus giao rõ cho bước merge, tách với lượt full suite lịch sử trước merge ở dưới.
- Các test dùng fixtures giả/local fake transports; chưa kiểm daemon/backend Paseo thật hoặc cập nhật runtime thật.

### Hand của bước merge

- Skill dùng lại: `hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md`.
- Trước mỗi hand, `pick --json` chọn codex / gpt-6.1-sol / low / gpt, skipped rỗng; chạy bằng `hand-ext run --backend auto --mode shell --isolation none` qua bin repo gốc. Không đổi config/order/account.
- Hand 1 giải conflict/test hẹp; hand 2 riêng chỉ chạy full suite, không sửa code/test. Hai wrapper đều exit 0, đã kết thúc/reap backend và test process trước bàn giao.
- Sol chỉ điều phối merge/commit, review và kiểm chứng; code/test thay đổi đều do hand thực hiện. Không có ngoại lệ tự code hay exit 7/8.

| Hand | Input (gồm cached) | Cached input | Output | USD~ offline |
|---|---:|---:|---:|---:|
| Giải conflict/test hẹp | 649596 | 605568 | 3907 | 0.187683 |
| Full suite riêng | 336378 | 301056 | 1403 | 0.114780 |

USD~ từ helper `token_price`/`estimate_cost` dùng canonical model-prices.json, không phải hoá đơn. Cả hai tool báo `used_percent=9.0`, reset `2026-11-16T06:19:22+00:00`; không tự suy window/quota từ token/USD.

- Report giải conflict: `output/llm/hand-ext/20261109-161426-423517-cfg-goi-a-merge-codex/report.md`.
- Report full suite: `output/llm/hand-ext/20261109-161914-544599-cfg-goi-a-merge-full-codex/report.md`.
- Tín hiệu hoàn tất mới: `/Users/anhtp/app/claude-plugins/docs/work-in-progress/handoffs/cfg-goi-a-merge.done`.

## Phạm vi và commit (Gói A trước merge main)

- Worktree: `/Users/anhtp/app/claude-plugins-wt/cfg-goi-a`.
- Nhánh: `side/cfg-goi-a`.
- Base: `6d3e9c7`.
- Commit: `9d4b23bf9ec988286adfc68d86b8abb1f6263ecc`.
- Commit subject: `feat(hybrid-hands): share layered global and repo configuration`.
- 11 file, 324 insertions, 59 deletions. Mọi đường dẫn `lib/` ở trên nằm dưới `hybrid-hands/plugins/hybrid-hands/`; `tests/` nằm dưới `hybrid-hands/`.
- Không sửa `hand_ext/run_cmd.py`, `report.py`, `hh_ps/codex.py`, `limits.py`: các nơi đó đã gọi adapter `load_config`/`load_ps_config`, nay tự nhận loader chung. Logic gắn cha PASEO_AGENT_ID/CODEX_THREAD_ID giữ nguyên.
- Chỗ đọc config riêng còn sót trong `usage_pricing.explicit_options` được phát hiện ở review và đã chuyển sang loader chung. Các `json.loads` còn lại đọc pricing canonical, state/metadata/ledger/manifest, không phải `hybrid-hands.json`.

## API để các gói sau dùng

`shared_config.load_config(cwd=None, *, known_root=None, config_file=None) -> ConfigResult`.

- `root`: repo hiện tại; giữ dự phòng config về repo chính khi worktree thiếu file riêng qua `_config_path` hiện có.
- `effective`: dict thô sau merge DEFAULTS ext_hand + side_session → global → repo. Dict merge sâu, list/scalar thay nguyên, không cache toàn cục.
- `sources`: dotted-key leaf → `plugin`, `global`, `repo`; empty dict cũng có nguồn, chuyển sang dict có children thì xoá nguồn leaf cũ.
- `paths`: `{global: {path, exists, read}, repo: {path, exists, read}}`; path tuyệt đối, ghi cả path mặc định khi file không có.
- `sections`: tuple `(source, raw_dict)` các file đã đọc, default `()`, phục vụ lấy override explicit mà không đọc file lần nữa. Không đọc nội dung file auth được trỏ bởi config_dir/home.
- `backends_from(result, backend)`: merge các backend option từ global/repo, không thêm plugin legacy price defaults. `usage_pricing.explicit_options` dùng API này, giữ explicit `null` là unknown.
- `GlobalConfigError` kế thừa `Exception`, chủ ý không phải `ValueError`, để các nhánh fallback repo hỏng trong hh_ps/report/limits không nuốt lỗi global. Ba CLI hand-ext, hh-ps, side-session in lỗi với path và trả khác 0.
- Validate object cho root, top-level section, ext_hand.backends/claude_accounts/go_usage và từng backend/account entry. Các leaf map như price_per_mtok được thay bằng `null`. Validate max_parallel sau merge theo kiểm tra hiện có.
- Cấu hình/path tương đối của consumer tính theo repo hiện tại. Registry claude_accounts giữ chuỗi thô để giữ compatibility; side-session resolve khi dùng; backend options resolve các path tương đối đã biết sau account/alias resolution.
- `hand-ext config --json [--cwd ...]`: JSON có `effective`, `sources`, `paths`; không doctor, không đọc file auth, không gọi live usage. CLI run `--effort` vẫn thắng.

## Kiểm chứng thật (lịch sử trước merge main)

Tất cả lượt test dùng HOME/HYBRID_HANDS_CONFIG tạm; các lượt cuối của Sol còn cô lập HYBRID_HANDS_STATE_DIR, CLAUDE_HOME và tắt Go live. Không tạo `~/.hybrid-hands/config.json` thật. Fixtures giả, không backend/network thật trong test.

### 3 ca mới

1. `test_precedence`: global effort thắng plugin, repo thắng global, CLI effort thắng repo; deep merge/list replace/provenance/empty dict, path backend tương đối, explicit pricing không lấy default và null leaf.
2. `test_missing_global`: thiếu file env override và thiếu file mặc định dưới HOME tạm vẫn chạy; inspect JSON có nguồn/paths.
3. `test_invalid_global`: JSON sai/root sai/section sai/backend-account entry sai; có path và exit !=0 tại hand-ext, hh-ps, side-session (gồm attach).

### Test hẹp cuối của Sol

```sh
PYTHONPATH=hybrid-hands/tests python3 -m unittest \
  test_shared_config test_hand_ext_parallel test_hand_ext_codex \
  test_hand_ext_usage test_hh_ps_codex test_hh_ps_gpt_nguon test_hh_ps_limits \
  test_hand_ext_config_worktree test_hand_ext_defaults test_side_session test_hh_ps_multirepo
```

- Kết quả: `Ran 81 tests in 6.318s`, `OK`, exit 0.
- HOME: `output/llm/cfg-goi-a/narrow-home-5yb5g_iq`; env global trỏ `absent-global.json` trong HOME đó.
- Log: `/Users/anhtp/app/claude-plugins-wt/cfg-goi-a/output/llm/cfg-goi-a/final-narrow.log`.
- `git diff --check`, `git diff --cached --check`: PASS; sau commit worktree sạch.
- Lượt hand trước: Codex 53 test hẹp PASS, lượt sửa Codex 55 PASS; dsh 81 PASS và 5 test hẹp riêng PASS. Kết quả Sol ở trên là kết quả cuối trên diff đã review.

### Full suite — đúng một lượt

```sh
python3 -m unittest discover -s hybrid-hands/tests -p 'test_*.py'
```

- Kết quả: `Ran 456 tests in 63.751s`, `FAILED (failures=2)`, exit 1.
- Log: `/Users/anhtp/app/claude-plugins-wt/cfg-goi-a/output/llm/cfg-goi-a/full-suite.log`.
- Lỗi 1: `CodexRunTest.test_usage_ledger_keeps_both_windows_and_estimates_once`: validator ép leaf price map phải object, từ chối explicit null. Đã sửa validator, test PASS trong nhóm 81 cuối.
- Lỗi 2: `ParallelTest.test_independent_scopes_and_config_validation`: mock `_read_section` không còn đi qua loader mới. Đã đổi test sang file fixture tạm thật; test PASS trong nhóm 81 cuối.
- Giới hạn ở bàn giao Gói A gốc: lượt full suite này diễn ra trước các sửa cuối của validator/explicit_options/test fixture. Không chạy lại trong yêu cầu gốc. Yêu cầu merge tiếp theo của Opus đã cho phép một hand riêng chạy một lượt full mới trên commit merge cuối; kết quả 490 PASS ở mục Merge main phía trên thay thế giới hạn này cho trạng thái hiện tại.

## Hand và review

Sol chỉ viết brief/review/bàn giao và điều phối commit; code/test đều do hand thực hiện.

- `pick --json` trả codex / gpt-6.1-sol / low / gpt, skipped rỗng trước mỗi lượt.
- Repo thực tế có `ext_hand.order = [codex, dsh, claude-v1, claude-v2]` (khác thứ tự mặc định trong policy). Không sửa order/config.
- Lượt 1 `run --backend auto --isolation none`: Codex, exit 0. Sol review phát hiện backend path tương đối và thiếu provenance empty dict; giao lại cùng backend đúng một lượt.
- Lượt 2 `run --backend auto --isolation none`: Codex, exit 0. Review/full suite vẫn phát hiện lỗi và config reader còn sót; chuyển backend kế tiếp dsh theo order repo.
- Lượt 3 `run --backend dsh --isolation none`: dsh, exit 0. Sol review toàn loader dựng lại và explicit_options, rồi tự chạy nhóm 81 test cuối PASS.
- Không gặp exit 7/8, không dùng ngoại lệ tự code, không mở side-session/subagent. Các process hand-ext/test do phiên tạo đều đã kết thúc.

| Lượt | Input (gồm cached) | Cached input | Output | USD~ offline |
|---|---:|---:|---:|---:|
| Codex đầu | 720444 | 670592 | 8008 | 0.246843 |
| Codex sửa | 274569 | 245376 | 3213 | 0.115054 |
| dsh cuối | 8037289 | 7941504 | 36442 | 0.120115 |

USD~ tính offline bằng helper estimate_cost/token_price từ canonical `config/model-prices.json`, tổng 0.482012 USD~, là ước tính subscription, không phải hoá đơn. Không suy quota từ token/USD.

- Codex tool báo `used_percent=2.0`, reset `2026-11-16T06:19:22+00:00`; không tự gắn nhãn window khi output lượt không ghi duration.
- dsh tool báo Go thật: 3% 5h (reset 18:39), 1% tuần (16/11 07:00), 15% tháng (04/12 15:17). Sổ ước tính riêng không dùng thay nguồn thật.
- Reports trong worktree, giữ nguyên:
  - `output/llm/hand-ext/20261109-141537-821787-cfg-goi-a-codex/report.md`
  - `output/llm/hand-ext/20261109-142216-680215-cfg-goi-a-review-codex/report.md`
  - `output/llm/hand-ext/20261109-142739-292830-cfg-goi-a-final-dsh/report.md`
- Skill áp dụng: `hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md`.

## Opus còn làm

- Đọc bàn giao và dùng API loader cho các gói B/C/E; chưa có key main_session/side_session.provider/native/transport mới.
- Merge nhánh sau khi đọc bàn giao; phiên Sol này không push/merge.
- Tài liệu/AGENTS/README/CHANGELOG/version và cập nhật cài đặt plugin qua công cụ chính thức do Opus thực hiện theo brief. Runtime thật chưa được cập nhật, vì vậy không claim phiên đang mở đã nạp code này.
- Chưa kiểm runtime dưới daemon Paseo với global thật; các kiểm chứng ở đây hoàn toàn local/fake và config tạm.
