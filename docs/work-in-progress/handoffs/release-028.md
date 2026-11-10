## Tóm tắt

- **XONG MỘT PHẦN**: code được Sol accepted; điều kiện mọi record đăng ký 0.28.0 chưa đạt.
- `dsh.py`: User-Agent lấy version manifest, kiểm chuỗi an toàn cho header, lỗi trả `unknown`.
- `test_hh_ps_codex.py`: regex reset nhận ngày `dd/mm` tùy chọn; `CHANGELOG.md`: thêm một bullet 0.28.0.
- Hai test hẹp: **2 tests / 0.042s / exit 0**. Full chạy đúng một lần: **415 tests / 45.726s / exit 0 / OK**.
- CLI cuối: **4/10 record đăng ký 0.28.0**, 6 worktree vẫn 0.27.0 dù update báo `up_to_date`; folderVersion cả 10 là 0.28.0.
- Validate manifest/plugin, build và reload plugin Paseo đạt; plugin enabled và running sau reload.
- Chưa kiểm GUI/điện thoại, chưa áp dụng vào phiên Claude đang mở; chưa kết luận nguyên nhân 6 record stale.
- Không commit/push. Token/quota: **?**.

## Thay đổi và review

So với baseline release-028, chỉ ba file source được giao thay đổi:

| File | Lý do và kết quả |
| --- | --- |
| `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/dsh.py` | Bỏ version User-Agent cứng; giữ API `USER_AGENT`, lấy manifest canonical, kiểm chuỗi header-safe, thiếu/hỏng trả `unknown`. |
| `hybrid-hands/tests/test_hh_ps_codex.py` | Chỉ mở regex assertion hiện hữu cho `HH:MM` và `dd/mm HH:MM`; không thêm test hay đổi fixture. |
| `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md` | Một bullet 0.28.0 về nguồn version User-Agent. |

Sol review và accepted code. Kiểm cuối ghi đúng ba file changed, `missing: []`, `diff --check` exit 0. Không đổi source panel, statusline, renderer, AGENTS hay manifest so baseline. Evidence: [final-source-check.json](../release-028/final-source-check.json), [hand-report.md](../release-028/hand-report.md).

## Lệnh và kết quả kiểm chứng

Hai test hẹp do hand chạy từ `/Users/anhtp/app/claude-plugins`:

```sh
PYTHONPATH=hybrid-hands/tests python3 -m unittest test_hand_ext_dsh.VersionTest.test_user_agent_matches_plugin_version test_hh_ps_codex.CodexPanelTest.test_codex_usd_pct_samples_and_gpt_account_limits -q
```

Kết quả: 2 tests, 0.042s unittest, exit 0. Evidence: [log](../release-028/hand-two-tests.log), [JSON](../release-028/hand-two-tests.json).

Sol chạy full đúng một lần, cùng cwd:

```sh
python3 -m unittest discover -s hybrid-hands/tests -q
```

Kết quả: 415 tests, 45.726s unittest, exit 0, OK. Bắt đầu UTC `2026-11-07T16:26:52`, kết thúc `2026-11-07T16:27:38`. Dòng doctor chưa đạt/codex skip và worktree kept thuộc fixture test; không phải full fail hoặc doctor runtime thật. Evidence: [log](../release-028/full-hybrid-hands.log), [JSON](../release-028/full-hybrid-hands.json).

Manifest JSON 0.28.0 hợp lệ, link nội bộ changelog không thiếu. Hai lệnh sau đều exit 0, validation passed:

```sh
claude plugin validate hybrid-hands
claude plugin validate hybrid-hands/plugins/hybrid-hands
```

Validator nhắc thiếu LICENSE/icon cho profile directory, không chặn local. Không mở rộng sửa ngoài brief.

## Cập nhật CLI và 10 record cuối

Sol chạy marketplace update exit 0, sau đó 10 lệnh plugin update tuần tự tại cwd của từng record; mọi lệnh exit 0:

```sh
claude plugin marketplace update hybrid-hands-local --json
claude plugin update hybrid-hands@hybrid-hands-local --scope <scope> --json
```

Bảng dưới ghi version đăng ký từ CLI cuối; `folderVersion` cả 10 record đều `0.28.0`. Cwd project/local là đường dẫn dưới `/Users/anhtp/app`; user record không có projectPath.

| Scope | Cwd / projectPath | Version đăng ký cuối | CLI update result |
| --- | --- | --- | --- |
| project | `/Users/anhtp/app/ai-comic-video` | 0.28.0 | updated, exit 0 |
| project | `/Users/anhtp/app/live-tiktok-games` | 0.28.0 | updated, exit 0 |
| local | `/Users/anhtp/app/ai-luxian` | 0.28.0 | updated, exit 0 |
| user | `/Users/anhtp/app/claude-plugins`; không projectPath | 0.28.0 | updated, exit 0 |
| project | `/Users/anhtp/app/live-tiktok-games-wt/RV-12c` | 0.27.0 | up_to_date; oldVersion/newVersion 0.28.0; exit 0 |
| project | `/Users/anhtp/app/live-tiktok-games-wt/RV-10b` | 0.27.0 | up_to_date; oldVersion/newVersion 0.28.0; exit 0 |
| project | `/Users/anhtp/app/live-tiktok-games-wt/WP-11` | 0.27.0 | up_to_date; oldVersion/newVersion 0.28.0; exit 0 |
| project | `/Users/anhtp/app/live-tiktok-games-wt/RV-10c` | 0.27.0 | up_to_date; oldVersion/newVersion 0.28.0; exit 0 |
| project | `/Users/anhtp/app/live-tiktok-games-wt/RV-13` | 0.27.0 | up_to_date; oldVersion/newVersion 0.28.0; exit 0 |
| project | `/Users/anhtp/app/live-tiktok-games-wt/RV-14` | 0.27.0 | up_to_date; oldVersion/newVersion 0.28.0; exit 0 |

CLI trước thấy 9 record 0.27.0 trong khi source folder 0.28.0; lần đọc sau có thêm RV-14. Không khẳng định ai tạo record mới. Sáu worktree đều được update tại đúng cwd với `--scope project` nhưng CLI list cuối vẫn 0.27.0; chưa kết luận nguyên nhân. Lệnh đọc CLI cuối exit 0. Không install/uninstall, không sửa tay registry/settings để lách giới hạn CLI.

Evidence: [installation-commands.json](../release-028/installation-commands.json), [installed-before.json](../release-028/installed-before.json), [installed-after.json](../release-028/installed-after.json), [installed-final.json](../release-028/installed-final.json), [installation-summary.json](../release-028/installation-summary.json).

## Build và reload Paseo

Sol dùng `node --input-type=module` gọi `compileDirectoryPlugin` của Paseo 0.15.0 trên source `/Users/anhtp/app/claude-plugins/hybrid-hands/paseo-hh-tree`. Script lưu ở [paseo-build.mjs](../release-028/paseo-build.mjs), gọi `esbuild.stop` trong `finally`. Build exit 0, client 20963 bytes, server 15657 bytes; hashes trong [paseo-build.json](../release-028/paseo-build.json), output ở [paseo-build.log](../release-028/paseo-build.log). Không sửa panel source.

```sh
paseo plugin reload hh-tree --json
paseo plugin ls hh-tree --json
```

Reload exit 0, xong UTC `2026-11-07T16:29:02`. Đọc sau reload exit 0: enabled `true`, status `running`, path `/Users/anhtp/app/claude-plugins/hybrid-hands/paseo-hh-tree`. Chỉ reload plugin, không daemon restart hoặc config reload. Evidence: [reload log](../release-028/paseo-reload.log), [reload JSON](../release-028/paseo-reload.json), [plugin trước](../release-028/paseo-plugin-before.json), [plugin sau](../release-028/paseo-plugin-after.json).

## Cách thực hiện và giới hạn

Native exception A được Sol kiểm gate: có `PASEO_AGENT_ID`, order chọn codex `gpt-6.1-sol` low, spawn hỗ trợ model/effort, `fork_turns=none`. Chỉ một hand cùng lúc, không vượt max 4; cùng hand làm code rồi docs tuần tự, Sol review. Áp dụng skill [ext-hand](../../../hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md) và [paseo](../../../hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md). Không có hand-ext ledger/meta/report; `hand-report.md` là báo cáo kỹ thuật, token/quota **?**.

Các tiến trình task tạo đã thoát; native child completed giữ history. Không đọc auth/.env, không dùng API key hoặc API trả phí; không commit/push. Bàn giao dựa trên kết quả kỹ thuật đã làm sạch do Sol cung cấp; lần viết docs này không chạy lại test/update/build/reload và chỉ kiểm existence của link evidence.

## Việc còn lại

- Sáu registry record worktree chưa lên 0.28.0 dù CLI update thành công: điều kiện mọi record 0.28.0 **chưa đạt**. Opus xử lý giới hạn CLI trong brief riêng nếu cần.
- Chưa kiểm GUI/điện thoại; không claim visual.
- CLI update báo “Restart to apply”; chưa tự restart các phiên Claude hiện hữu.
- Marker release-028.done do Sol tạo sau khi review bàn giao; marker kết thúc phiên, không đồng nghĩa mọi record đã cập nhật.
