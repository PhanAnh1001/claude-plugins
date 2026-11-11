# Action plan-status

## Tóm tắt

- **Mục đích:** composite GitHub Action dùng chung để repo bất kỳ tự sinh lại trang tình hình plan
  (`dw plan-status`) và chỉ commit khi nội dung thật sự đổi (bỏ qua thay đổi chỉ ở dòng "Cập nhật ").
- **Cách dùng nhanh:** trong repo đích chạy `dw plan-status init --repo .` (xem trước) rồi `--write`;
  lệnh sinh `.claude/plan-status.toml`, `.github/workflows/plan-status.yml` và luật AGENTS.md.
- **Bắt buộc:** workflow cần `permissions: contents: write`; người push file workflow cần token có scope
  `workflow`; ghim tag `plan-status-v1` (hoặc SHA commit).

## Workflow mẫu

```yaml
name: plan-status
on:
  push:
    branches: [main]
    paths: ["docs/plans/*.md", ".claude/plan-status.toml", ".github/workflows/plan-status.yml"]
  schedule:
    - cron: '17 */6 * * *'
  workflow_dispatch:
permissions:
  contents: write
concurrency:
  group: plan-status
  cancel-in-progress: false
jobs:
  plan-status:
    runs-on: ubuntu-latest
    steps:
      - uses: PhanAnh1001/claude-plugins/dev-workflow/actions/plan-status@plan-status-v1
```

## Inputs

| Input | Mặc định | Ý nghĩa |
|---|---|---|
| `branch` | `main` | Nhánh nhận commit cập nhật |
| `python-version` | `3.11` | Python ≥ 3.11 |
| `commit-message` | `docs(status): tự cập nhật trang tình hình` | Thông điệp commit |
| `config` | `.claude/plan-status.toml` | File cấu hình trang |

## Hành vi

1. Checkout `fetch-depth: 0` để có lịch sử và `refs/remotes/origin/*`.
2. Kiểm mọi `ref` của `[[page]]` tồn tại; thiếu thì báo `::error::` và dừng.
3. Chạy `plan_status.py --repo .` với `TZ=Asia/Ho_Chi_Minh` (script lấy từ chính repo Action, không checkout thứ hai).
4. Có dòng đổi thật hoặc file mới trong `out_dir` thì commit bằng `github-actions[bot]`,
   `git pull --rebase` rồi push; xung đột thì fail, không ép push.
