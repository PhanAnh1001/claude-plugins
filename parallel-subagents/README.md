# claude-plugins

Marketplace tự host (`parallel-subagents-local`) cho Claude Code, hiện chứa một plugin:

- **`parallel-subagents`** — điều phối subagent song song: worker `parallel-subagents:hand` chạy song song, brain chia việc, review và
  tổng hợp. Plugin gồm agent `hand` và một `UserPromptSubmit` hook bơm policy
  brain/hand vào context ở mỗi prompt.

## Cài đặt

### 1. Từ local (máy đã có sẵn repo này)

Trong Claude Code:

```
/plugin marketplace add <thư-mục-repo>/parallel-subagents
/plugin install parallel-subagents@parallel-subagents-local
```

Gốc marketplace là thư mục `parallel-subagents/` bên trong repo `claude-plugins` (không phải gốc repo).
Cây thư mục:

```
claude-plugins/                      # gốc repo git
└── parallel-subagents/              # gốc marketplace — đường dẫn đưa cho `marketplace add`
    ├── .claude-plugin/marketplace.json   # source: ./plugins/parallel-subagents (tương đối với gốc marketplace)
    ├── README.md
    └── plugins/parallel-subagents/
        ├── .claude-plugin/plugin.json
        ├── agents/hand.md                # sửa agent hand ở đây
        ├── hooks/hooks.json              # khai báo hook
        ├── scripts/inject-policy.sh
        ├── scripts/session-start-policy.sh
        └── templates/hand-brief.md
```

### 2. Từ git (clone repo `claude-plugins`)

Plugin không có git repo riêng: nó nằm trong repo `claude-plugins`
(`https://github.com/PhanAnh1001/claude-plugins`; xem README gốc repo). Clone repo `claude-plugins` rồi add thư mục con như mục 1:

```sh
git clone https://github.com/PhanAnh1001/claude-plugins.git <thư-mục-repo>
claude plugin marketplace add <thư-mục-repo>/parallel-subagents
claude plugin install parallel-subagents@parallel-subagents-local --scope user
```

### 3. Từ internet, không dùng git (marketplace host qua HTTPS)

Claude Code tách biệt hai thứ: **nguồn của marketplace** (nơi lấy file
`marketplace.json`) và **nguồn của từng plugin** (nơi lấy code plugin). Cả hai đều
có thể là một URL HTTPS thuần, không cần git server.

- Marketplace source qua URL: trỏ thẳng tới file `marketplace.json` được host tĩnh
  (S3, GitHub Pages, Artifactory, nginx...):

  ```
  /plugin marketplace add https://example.com/claude-plugins/marketplace.json
  /plugin install parallel-subagents@parallel-subagents-local
  ```

- Khi marketplace được add theo kiểu URL, trường `source` của từng plugin trong
  `marketplace.json` **không được để relative path** (`"./plugins/..."`) vì không có
  gì để resolve theo — phải dùng một trong các kiểu source object dưới đây.

Người dùng có thể khai báo sẵn marketplace này (không cần chạy `/plugin marketplace
add` thủ công) qua Claude Code settings:

```json
{
  "extraKnownMarketplaces": [
    { "source": "url", "url": "https://example.com/claude-plugins/marketplace.json" }
  ]
}
```

### 4. Từ file zip local (không cần host, không cần internet)

Có hai cách dùng file `.zip` local, tuỳ có muốn cài **vĩnh viễn** hay chỉ **thử trong
một phiên**.

- **Chỉ cho phiên hiện tại** (nhanh nhất, dùng khi test): flag `--plugin-dir` nhận cả
  thư mục lẫn file `.zip`, nạp thẳng plugin mà không cần marketplace:

  ```
  claude --plugin-dir ./parallel-subagents-2.0.0.zip
  ```

  Không ghi vào settings — lần chạy `claude` sau sẽ không còn plugin này. Nếu đã có
  plugin cùng tên cài qua marketplace, bản `--plugin-dir` sẽ ưu tiên hơn trong phiên
  đó (trừ plugin bị managed settings ép bật/tắt).

- **Cài vĩnh viễn**: giải nén zip ra một thư mục rồi add thư mục đó làm local
  marketplace, giống mục "Cài đặt > 1":

  ```
  unzip parallel-subagents-2.0.0.zip -d ./parallel-subagents-local
  /plugin marketplace add ./parallel-subagents-local
  /plugin install parallel-subagents@parallel-subagents-local
  ```

  Thư mục giải nén phải chứa `.claude-plugin/marketplace.json` (source của plugin
  trong đó dùng relative path như `"./plugins/parallel-subagents"`, giống mục "Cài đặt > 1"),
  hoặc chính là thư mục plugin (chứa `.claude-plugin/plugin.json`) nếu add trực tiếp
  path đó làm nguồn plugin trong một marketplace.json khác.

> Lưu ý: trường `archive` trong `marketplace.json` (Cách A ở mục dưới) chỉ chấp nhận
> `url` dạng `https://` — không có cú pháp `file://` cho zip local, và Claude Code từ
> chối cả `http://` lẫn host loopback/nội bộ. Muốn cài từ zip mà không host ở đâu cả,
> phải dùng một trong hai cách ở trên.

## Đưa plugin mới lên internet (không dùng git)

Có hai cách để một plugin cài được thẳng từ HTTPS thay vì clone git repo. Cả hai đều
sửa trường `source` của plugin đó trong `.claude-plugin/marketplace.json`.

### Cách A — Archive: đóng gói zip, host tĩnh

1. Đóng gói thư mục plugin thành zip. Nội dung zip phải nằm ở gốc hoặc trong đúng
   một thư mục con top-level (không được lồng sâu hơn), tối đa 256 MiB:

   ```
   cd plugins/parallel-subagents && zip -r ../../dist/parallel-subagents-2.0.0.zip . -x '.*'
   ```

2. Tính sha256 của file zip:

   ```
   shasum -a 256 dist/parallel-subagents-2.0.0.zip
   ```

3. Upload zip lên bất kỳ nơi host HTTPS tĩnh nào (S3/R2/GitHub Releases/Artifactory...).
   Bắt buộc `https://` — Claude Code từ chối `http://`, loopback và các host nội bộ.

4. Sửa entry plugin trong `marketplace.json`, thay `source` string bằng object
   `archive`, kèm `version` để client biết khi nào cần tải lại:

   ```json
   {
     "name": "parallel-subagents",
     "version": "1.0.0",
     "source": {
       "source": "archive",
       "url": "https://example.com/claude-plugins/parallel-subagents-2.0.0.zip",
       "sha256": "<sha256 vừa tính>"
     },
     "description": "..."
   }
   ```

5. Publish `marketplace.json` đã sửa lên cùng chỗ host ở mục "Cài đặt > 3" (hoặc
   commit lên git nếu vẫn muốn dùng git chỉ cho marketplace, còn plugin thì tải qua
   HTTPS). Mỗi lần đổi code plugin: build zip mới, tính sha256 mới, **tăng `version`**
   — nếu không, client đang có bản cache cũ sẽ không tải bản mới.

Yêu cầu Claude Code >= v2.1.224. Nếu `sha256` khai sai, cài đặt sẽ báo lỗi toàn vẹn
dữ liệu (`Plugin archive integrity check failed`) thay vì âm thầm cài bản hỏng.

### Cách B — npm: publish plugin như một gói npm

```
cd plugins/parallel-subagents && npm publish
```

Rồi trỏ `source` sang:

```json
{
  "source": {
    "source": "npm",
    "package": "parallel-subagents-plugin",
    "version": "1.0.0"
  }
}
```

`registry` tuỳ chọn nếu dùng npm registry riêng (private registry nội bộ). Cách này
phù hợp khi plugin đã có sẵn quy trình publish npm; Cách A phù hợp hơn khi chỉ cần
một nơi host file tĩnh, không phụ thuộc npm registry.

> Cả hai cách đều nên chạy `claude plugin validate` trên `marketplace.json` trước khi
> publish để bắt lỗi manifest sớm.

## Ghi chú sau khi cài

Sau khi cài và xác nhận hook của plugin thật sự chạy (policy xuất hiện trong context ở
mỗi prompt), nên dọn các nguồn trùng lặp để tránh hai nguồn policy/agent lệch nhau:

- Gỡ hook `UserPromptSubmit` trùng lặp trong `~/.claude/settings.json`.
- Có thể xoá `~/.claude/agents/hand.md` (agent `hand` đã do plugin cung cấp).

## Chuyển plugin sang máy khác

Gói `parallel-subagents-plugin.zip` chứa toàn bộ marketplace (kể cả `.claude-plugin/marketplace.json`),
nên máy đích chỉ cần giải nén rồi add thư mục đó làm local marketplace.

### 1. Giải nén và khôi phục quyền thực thi

Giải nén vào một thư mục bất kỳ trên máy đích, ví dụ `<thư-mục-repo>/parallel-subagents`:

```
unzip parallel-subagents-plugin.zip -d <thư-mục-repo>/parallel-subagents
```

Hook `UserPromptSubmit` gọi `scripts/inject-policy.sh`; nếu mất bit execute thì hook **im lặng
không chạy** mà không báo lỗi. Đặt lại cho chắc:

```
chmod +x <thư-mục>/plugins/parallel-subagents/scripts/inject-policy.sh
```

### 2. Cài marketplace và plugin

Từ shell:

```
claude plugin marketplace add <thư-mục>
claude plugin install parallel-subagents@parallel-subagents-local
```

Scope mặc định là `user`. Trong một phiên Claude Code đang mở, hai lệnh tương đương là
`/plugin marketplace add <thư-mục>` và `/plugin install parallel-subagents@parallel-subagents-local`.

### 3. Kiểm chứng

```
claude plugin marketplace list
claude plugin list
```

Kết quả mong đợi: `parallel-subagents-local  Source: Directory (<thư-mục>)` ở lệnh thứ nhất, và
`parallel-subagents@parallel-subagents-local  Version: 2.0.0  Scope: user  Status: enabled` ở lệnh thứ hai.
Sau đó khởi động lại Claude Code và kiểm tra agent `hand` đã xuất hiện trong danh sách agent.

### 4. Cảnh báo: bản cache không tự đồng bộ

Marketplace kiểu `directory` **chép** plugin sang bản cache tại
`~/.claude/plugins/cache/parallel-subagents-local/parallel-subagents/2.0.0/`, và bản cache đó **không tự cập
nhật** khi file nguồn đổi. Mọi lần sửa file nguồn (điển hình là `agents/hand.md`) đều phải chép
đè sang cache rồi khởi động lại Claude Code:

```
cp <thư-mục>/plugins/parallel-subagents/agents/hand.md \
   ~/.claude/plugins/cache/parallel-subagents-local/parallel-subagents/2.0.0/agents/hand.md
diff <thư-mục>/plugins/parallel-subagents/agents/hand.md \
     ~/.claude/plugins/cache/parallel-subagents-local/parallel-subagents/2.0.0/agents/hand.md
```

`diff` phải không in ra gì. Bỏ bước này thì agent `hand` vẫn chạy bản cũ, kể cả sau khi khởi
động lại — đây là nguyên nhân thật của các lần "luật mới đã viết nhưng hand không tuân thủ".

Trạng thái xác minh (2026-10-07): **chưa xác minh** bản nào được nạp lúc chạy. Bằng chứng trái chiều:
`claude plugin list` báo `Read from: <thư-mục>/plugins/parallel-subagents` (nguồn), trong khi
`~/.claude/plugins/installed_plugins.json` ghi `installPath` là thư mục cache trên, và cache là bản
chép thật (thư mục thường, không phải symlink). Cho tới khi kiểm được, cứ chép đè + `diff` như trên.

### 5. Không cần chép tay file state của CLI

`~/.claude/plugins/known_marketplaces.json` và `installed_plugins.json` do CLI tự sinh khi chạy
hai lệnh ở bước 2 — không chép tay từ máy cũ sang. Nếu muốn khai báo sẵn bằng tay thay vì chạy
lệnh, dùng hai khoá trong `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "parallel-subagents@parallel-subagents-local": true
  },
  "extraKnownMarketplaces": {
    "parallel-subagents-local": {
      "source": { "source": "directory", "path": "<thư-mục>" }
    }
  }
}
```

Lưu ý `extraKnownMarketplaces` ở đây là một **object** keyed theo tên marketplace, không phải
array.
