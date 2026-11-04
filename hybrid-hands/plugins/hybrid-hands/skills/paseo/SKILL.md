---
name: paseo
description: Dùng Paseo (daemon + CLI + app điện thoại) để theo dõi và điều khiển phiên brain/hand từ xa - cài đặt, khởi và dừng daemon, ghép điện thoại (người dùng tự làm), chạy hand Codex với CODEX_HOME riêng (~/.codex-hand, đăng nhập gói ChatGPT, không API key) qua provider tuỳ biến, theo dõi bằng ls/logs/wait/send, và giới hạn (phiên claude mở ngoài Paseo không tự hiện). Từ khoá kích hoạt - "paseo", "điện thoại", "theo dõi phiên", "điều khiển từ xa", "ghép điện thoại", "pair", "xem hand trên điện thoại", "daemon paseo".
---

# Paseo: theo dõi và điều khiển phiên từ điện thoại

## Tóm tắt

- **Là gì:** Paseo là daemon cục bộ + CLI + app (điện thoại, desktop, web) để chạy và điều khiển agent Claude Code, Codex... dùng lại đăng nhập sẵn có của từng CLI; Apache-2.0, bản dùng ở đây **0.15.0** (npm `latest` 04/11/2026) ([repo](https://github.com/getpaseo/paseo), 11/2026; [docs](https://paseo.sh/docs), 11/2026).
- **Đã cài:** `npm install -g @getpaseo/cli@0.15.0`, `paseo --version` in `0.15.0` (kiểm trên máy 04/11/2026).
- **Daemon:** `paseo start` chạy nền, nghe `127.0.0.1:6767`, cấu hình ở `~/.paseo/config.json`; relay (để điện thoại kết nối qua internet) **tắt mặc định**. Không thấy cơ chế tự khởi động khi đăng nhập máy.
- **Hand Codex riêng:** khai provider tuỳ biến `codex-hand` (`extends: "codex"`, `env.CODEX_HOME`) trong config, `paseo reload`, rồi `paseo run --provider codex-hand ...`; hoặc một lần bằng `paseo run --provider codex --env CODEX_HOME=...`.
- **Giới hạn chính:** chỉ agent do Paseo tạo (hoặc `paseo import <session-id>`) mới hiện; phiên `claude` brain đang chạy trong terminal và phiên `screen` của side-session **không tự hiện** (đã kiểm: `paseo ls -a -g` rỗng khi có phiên claude đang mở).
- **Người dùng phải tự làm:** bật relay, quét QR trên điện thoại, cài app; agent không ghép điện thoại hộ, không ghi `~/.paseo/config.json` khi chưa được duyệt.

## 1. Cài đặt và phiên bản

- Cài ghim bản: `npm install -g @getpaseo/cli@0.15.0` ([docs](https://paseo.sh/docs), 11/2026). Kiểm: `paseo --version`.
- npm 11 bỏ qua install script của `node-pty`, `esbuild`, `msgpackr-extract` (cảnh báo `allow-scripts` khi cài, 04/11/2026). Daemon và CLI vẫn chạy; nếu terminal trong app lỗi thì cài lại kèm `--allow-scripts=esbuild,node-pty,msgpackr-extract` (người dùng quyết).
- Paseo dùng `codex`, `claude` có trên `PATH` của daemon; kiểm bằng `paseo provider diagnostic codex` (trên máy: `/Users/anhtp/.local/bin/codex`, `codex-cli 0.150.1`, Status Ready) ([docs Codex](https://paseo.sh/docs/codex), 11/2026).

## 2. Daemon

- **Khởi:** `paseo start` (đọc `~/.paseo/config.json`, tự tạo nếu chưa có), in PID, địa chỉ nghe và đường log. `paseo onboard` = cài đặt lần đầu + khởi daemon + in hướng dẫn ghép (`--port` mặc định 6767, `--relay`/`--no-relay`, `--no-mcp`) (`paseo onboard --help`, 0.15.0).
- **Xem/dừng:** `paseo status` (dòng `localDaemon: running|stopped`), `paseo daemon stop`, `paseo daemon restart` (cần sau khi đổi `daemon.listen`), `paseo reload` (đọc lại config, đủ cho đổi provider) ([connectivity](https://paseo.sh/docs/connectivity), 11/2026; [custom providers](https://paseo.sh/docs/custom-providers), 11/2026).
- **Cổng:** `127.0.0.1:6767`; config mặc định sinh ra có `daemon.relay.enabled: false`, CORS cho `https://app.paseo.sh` (đã kiểm với `--home` tạm 04/11/2026).
- **Thử không đụng config thật:** mọi lệnh nhận `--home <dir>`; dùng thư mục tạm để thử rồi `paseo daemon stop --home <dir>`.
- **Tự khởi động:** docs không nói daemon CLI tự chạy khi đăng nhập; app desktop thì tự khởi daemon kèm theo ([docs](https://paseo.sh/docs), 11/2026). Muốn luôn chạy thì người dùng tự thêm (ví dụ launchd) — chưa làm.

## 3. Ghép điện thoại (người dùng tự làm)

Agent chỉ được nhắc các bước, không chạy hộ (bật relay mở đường vào máy từ internet).

1. Cài app Paseo trên điện thoại (link tải ở [paseo.sh](https://paseo.sh), 11/2026).
2. Trên Mac: `paseo daemon pair` (hoặc `paseo pair --relay` để bật relay không hỏi); xác nhận bật relay — traffic relay mã hoá đầu-cuối ([connectivity](https://paseo.sh/docs/connectivity), 11/2026).
3. Trên điện thoại: quét QR, hoặc "Paste pairing link" dán link CLI in ra.
4. Không muốn relay: cho điện thoại vào cùng Tailscale, đặt `daemon.listen` thành IP Tailscale (`tailscale ip -4`) + `:6767`, `paseo daemon restart`; có thể đặt mật khẩu `paseo daemon set-password` ([connectivity](https://paseo.sh/docs/connectivity), 11/2026).

## 4. Chạy hand Codex với CODEX_HOME riêng

Paseo dùng lại đăng nhập gói của CLI, không cần API key. `~/.codex` là đăng nhập ChatGPT chính của người dùng; hand dùng `~/.codex-hand` (gói ChatGPT riêng cho hand, cùng thư mục với backend `codex` của `hand-ext`).

- **Cách nên dùng — provider tuỳ biến** (đề xuất; người dùng duyệt rồi mới ghi vào `~/.paseo/config.json`, sau đó `paseo reload`) ([custom providers](https://paseo.sh/docs/custom-providers), 11/2026):

```json
{
  "agents": {
    "providers": {
      "codex-hand": {
        "extends": "codex",
        "label": "Codex hand (gói ChatGPT)",
        "env": { "CODEX_HOME": "/Users/anhtp/.codex-hand" },
        "models": [
          { "id": "<model id GPT-6.1 Sol trong ~/.codex-hand>", "label": "GPT-6.1 Sol", "isDefault": true }
        ]
      }
    }
  }
}
```

  Rồi: `paseo provider models codex-hand` (kiểm model), `paseo run --provider codex-hand --title hand-x --no-wait "$(cat brief.md)"`.
- **Một lần, không sửa config:** `paseo run --provider codex --env CODEX_HOME=/Users/anhtp/.codex-hand --model <id> --no-wait "..."` (`--env`, `--model`, `--provider provider/model` có trong `paseo run --help`, 0.15.0). Danh sách model của provider `codex` mặc định lấy từ `~/.codex` nên có thể không có GPT-6.1 Sol (trên máy chỉ thấy `gpt-5.6-terra`, `gpt-5.6-luna`) — vì vậy ưu tiên provider tuỳ biến.
- **Cấu hình model:** đặt `model` mặc định trong `~/.codex-hand/config.toml` (`hand-ext setup --backend codex` ghi sẵn; CODEX_HOME riêng nên không ảnh hưởng `~/.codex`). Trường `command` của provider thay toàn bộ lệnh khởi nhưng Paseo tự thêm subcommand nên chèn profile `-p` **chưa kiểm**, đừng dùng khi chưa thử.
- **Hạn mức:** mỗi `paseo run` với hand dùng hạn mức gói ChatGPT của `~/.codex-hand`; theo dõi bằng `hand-ext status`, luật như skill `ext-hand`.

## 5. Theo dõi và điều khiển

Theo [orchestration](https://paseo.sh/docs/orchestration) (11/2026) và `--help` 0.15.0:

| Việc | Lệnh |
|---|---|
| Liệt kê agent (kể cả lưu trữ, mọi thư mục) | `paseo ls -a -g` |
| Xem nhật ký | `paseo logs <id> --tail 10` (`-f` theo dõi, `--filter tools|text|errors|permissions`) |
| Chờ xong có trần | `paseo wait <id> --timeout 60` |
| Gửi thêm việc | `paseo send <id> "..."` (`--prompt-file`, `--behavior steer|interrupt`, `--no-wait`) |
| Chi tiết / dừng / xoá | `paseo inspect <id>`, `paseo stop <id>`, `paseo archive <id>` |
| Duyệt quyền chờ | `paseo permit ...` |

- Id nhận tiền tố. Không viết vòng chờ không trần; dùng `paseo wait --timeout`.
- Agent trong Paseo gọi agent khác qua tool MCP `create_agent`, `send_agent_prompt` khi bật `daemon.mcp.injectIntoAgents` ([MCP](https://paseo.sh/docs/mcp), 11/2026).

## 6. Giới hạn: phiên nào hiện

- **Hiện:** agent tạo bằng `paseo run`, app, MCP; và phiên provider nhập vào bằng `paseo import <session-id> --provider claude|codex --cwd <dir>` (`paseo import --help`, 0.15.0).
- **Không tự hiện:** phiên `claude` brain mở trong terminal, phiên `screen` của side-session, hand chạy qua `hand-ext` ngoài Paseo. Bằng chứng: daemon thử 04/11/2026, `paseo ls -a -g` rỗng trong khi phiên claude brain đang chạy. `import` tạo agent Paseo nối tiếp session đó, không phản chiếu trực tiếp terminal đang mở (suy luận từ mô tả lệnh, chưa thử).
- Muốn xem brain trên điện thoại thì brain phải chạy trong Paseo (tạo bằng `paseo run --provider claude`) hoặc import.
