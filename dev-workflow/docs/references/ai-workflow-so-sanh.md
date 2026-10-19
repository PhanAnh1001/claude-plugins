# So sánh AI Workflow (deck tham khảo) với dev-workflow: những điểm có thể học

Nguồn so sánh: [ai-workflow-deck.md](ai-workflow-deck.md) (bản Markdown của deck "AI Workflow – Quy trình phát triển
dự án cùng AI"; số "slide N" dưới đây theo thứ tự trong file đó) và plugin `dev-workflow` 0.5.0 trong repo này.
Đường dẫn tính từ thư mục `dev-workflow/`. Ngày so sánh: 2026-10-19.

## Tóm tắt

- **Hai workflow bổ sung cho nhau, không thay thế nhau.**
  - **AI Workflow** là mô hình vận hành cho cả team. Kit luật dùng chung được phát từ một nguồn. Người và AI chung một
    board. Ba agent BA, Dev, QA tự nhận việc theo cột, chạy cả đêm; người giữ các cổng.
  - **dev-workflow** là kỷ luật cho từng phiên làm việc của dev cùng một agent (hoặc brain/hand). Gồm lane L0-L3 đo
    được, điều tra lỗi bằng test đỏ, đo đạc có bằng chứng, truy vết FR → task → test bằng script, living docs, self-review
    và closeout.
  - Theo lộ trình của deck (slide 12), dev-workflow đang ở **mức 1: "chỉ dùng kit, chưa bật agent"**.
- **Nên giữ, vì dev-workflow chi tiết hơn deck:** tiêu chí lane C1-C9, quy trình điều tra lỗi, chuẩn đo đạc, trace check
  có mã thoát, `docs_map`, self-review, resume-work, công thức estimate và log giờ thật lên Jira.
  Deck chỉ nêu ý ở các mảng này, không mô tả cơ chế.
- **12 điểm có thể học, chia 5 nhóm và 3 mức ưu tiên:**
  - **Ưu tiên 1 (làm được ngay trong plugin, chi phí thấp):**
    - A2: luật bất biến.
    - B1: block tiến độ chỉ nối thêm trên ticket Jira, cùng báo cáo chờ người/bị chặn.
    - B2: hợp đồng agent, nhãn `needs-human` và block handoff.
    - C1: chế độ chạy (agent tự chạy / duyệt từng bước / người cầm lái) song song với lane.
    - C2: trần 3 vòng tự sửa khi gate đỏ.
    - D1: đồng bộ quyết định mới vào SRS ngay khi phát sinh.
  - **Ưu tiên 2 (cần skill hoặc template mới):**
    - A1: luật phân tầng core → pack → module → cá nhân.
    - D2: chuỗi PRD → SRS → test case có mã TC.
    - D3: duyệt thay đổi tài liệu theo lô, chỉ trên phần khác.
    - E1: skill khôi phục tài liệu cho dự án cũ.
    - E2: skill release kèm định nghĩa Done.
  - **Ưu tiên 3 (cần hạ tầng, cân nhắc sau):** A3, agent tự nhận việc trên board, chạy đêm, worktree riêng, giới hạn
    merge request chờ review, trần chi phí AI, hỗ trợ Codex.
- **Không chép nguyên:**
  - Cơ chế chạy 24/7 không người trông: repo đích chưa có CI chạy test, nên gate vẫn dựa vào agent tự chạy
    (`docs/skill-proposal.md`).
  - Các chi tiết gắn với Linkup và GitLab.
  - Mã ticket và giờ giấc trong deck: chỉ là minh hoạ.
- **Người đọc cần làm:** chọn các mục ưu tiên 1 muốn đưa vào bản 0.6.0. Mỗi mục được chọn sẽ thành một task trong plan
  mới ở `docs/plans/` (lane L2, vì chạm nhiều skill).

## 1. Hai workflow nhìn tổng thể

| Khía cạnh | AI Workflow (deck) | dev-workflow (repo này) |
|---|---|---|
| Phạm vi | Cả team: PO, PM, BA, Dev, QA, Tech Lead; nhân rộng sang team khác bằng pack (slide 5, 31) | Một dev với một agent hoặc brain/hand; team chỉ hiện qua Jira và cổng duyệt (`README.md`) |
| Công cụ AI | Claude Code và Codex (slide 1, 5) | Chỉ Claude Code (`plugins/dev-workflow/.claude-plugin/plugin.json`) |
| Nơi theo dõi việc | Board Linkup qua MCP, người và AI chung một Kanban (slide 6) | Jira qua `jira-cli` của plugin `jira-tools` (skill `jira-workflow`) |
| Phân loại việc | Ba mức giao việc theo độ rõ và độ khó (slide 22) | Lane L0-L3 theo 9 tiêu chí đo được (skill `dev-triage`) |
| Tác nhân | Ba agent theo vai: BA nhận To Do, Dev nhận Ready, QA nhận Test Review (slide 10, 13) | Một agent; brain chia việc, hand thực thi (plugin `parallel-subagents`) |
| Kích hoạt | Agent tự quét board, chạy song song, chạy cả đêm (slide 28) | Người gọi trong phiên; chỉ tự chạy lại khi resume sau lỗi (skill `resume-work`) |
| Tài liệu | PRD → SRS → test case → ticket → MR → bằng chứng QA (slide 17) | SRS (ai4ba) → design → plan → test, liên kết bằng ID FR/NFR/BR (`docs/ai-dev-workflow.md`) |
| Cổng của người | Chốt ý tưởng, duyệt spec, quyết định khó đảo ngược, merge, deploy (slide 31) | Nguyên nhân gốc (L1 bug), design/plan (L2), review diff, kết quả đo (L3) |
| Phân phối luật | Kit trên GitLab, luật phân tầng, hook tự cập nhật (slide 4, 5) | Marketplace cục bộ; tăng `version`, người dùng tự update (`README.md`) |
| Mức độ hiện thực | Deck trình bày tầm nhìn; ghi "đã chạy thật ở quy mô một người" (slide 31) | Plugin đã chạy: 12 skill, 7 template, script và bộ test |

## 2. Điểm dev-workflow đang mạnh hơn: giữ nguyên

Deck có nhắc tới các mảng dưới đây nhưng không mô tả cơ chế. Khi học từ deck, không được làm yếu các phần này.

| Mảng | dev-workflow có | Deck chỉ nói |
|---|---|---|
| Phân loại việc | 9 tiêu chí C1-C9; nằm giữa hai lane thì chọn lane cao hơn; bug không bao giờ là L0 | "việc nhỏ, rõ" và "việc lớn, khó" (slide 18, 22) |
| Điều tra lỗi | Tái hiện, test đỏ vì assertion, git log/blame/bisect, báo nguyên nhân gốc, dừng chờ duyệt | "Điều tra bug có bằng chứng" (slide 4) |
| Đo đạc | Đổi một biến mỗi lần, n ≥ 3, cùng harness, số thô kèm median, hash để kiểm tất định | "Đo được" ở mức quản lý (slide 31) |
| Truy vết | `dw trace` quét SRS, plan và tên test; có waiver; mã thoát 0/1/2 | Chuỗi truy vết là ý tưởng, chưa có công cụ kiểm (slide 17) |
| Living docs | Chỉ giữ thiết kế hiện hành; `docs_map` ánh xạ code sang docs; closeout kiểm độ phủ | "Tài liệu luôn khớp thực tế" (slide 30) |
| Tự kiểm trước khi xong | Self-review từng mục, kết luận CONFIRMED / needs-fix / n/a kèm bằng chứng | "Tự review" (slide 31) |
| Phục hồi | `resume-work` dựng lại trạng thái từ plan, git và transcript | Block handoff khi agent bỏ dở (slide 28) |
| Jira | Tìm trước khi tạo, dry-run, estimate theo công thức, log giờ thật từ transcript | create-task hỏi lại và tìm trùng (slide 27), tương đương phần tìm trước khi tạo |

## 3. Điểm có thể học

Mỗi điểm ghi theo bốn ý: deck làm gì, dev-workflow hiện có gì, đề xuất, và ưu tiên.

### A. Phân phối và tầng luật

- **A1. Luật phân tầng: core → pack → module → cá nhân, luật riêng thắng luật chung (slide 4, 5).**
  - **Hiện có:** config repo đè giá trị mặc định (`dw_config.py`); template của repo đè template của plugin
    (`dw_template.py`). Chưa có tầng "pack theo vị trí" (BA, QA) hay "luật riêng theo module".
  - **Đề xuất:** cho `[docs_map]` hoặc một mục mới `[modules]` trỏ tới file luật của từng module. Skill nạp luật module
    khi diff chạm module đó. Ghi rõ thứ tự ưu tiên giữa các tầng trong README.
  - **Ưu tiên:** 2.
- **A2. Luật bất biến: không tầng nào được nới (slide 4).**
  - **Hiện có:** các luật như "không commit/push khi chưa được yêu cầu" và "không in PAT" nằm rải trong từng skill.
  - **Đề xuất:** gom thành một danh sách luật bất biến trong một reference dùng chung, nạp qua hook SessionStart. Config
    repo không được tắt các luật này.
  - **Ưu tiên:** 1.
- **A3. Tự cập nhật kit: mọi máy nhận bản mới ở phiên kế tiếp (slide 5).**
  - **Hiện có:** người dùng phải tự chạy marketplace update và plugin update (`README.md`).
  - **Đề xuất:** kiểm tra cơ chế tự cập nhật marketplace của Claude Code. Nếu không có, cho hook SessionStart so
    `version` đã cài với nguồn và nhắc người dùng cập nhật.
  - **Ưu tiên:** 3.

### B. Theo dõi công việc trên ticket

- **B1. Block tiến độ chỉ nối thêm (slide 6, 25, 28).**
  - **Deck:** mỗi bước nối một block `[spec #1]`, `[duyệt]`, `[merge request]`, `[QA đạt]`, `[release]` vào mô tả
    ticket, ghi ai làm và bằng chứng. Block chỉ nối thêm, không sửa, không xoá. PM đọc báo cáo ngày tổng hợp từ các
    block: đã xong, chờ người, bị chặn.
  - **Hiện có:** `jira-workflow` chỉ cập nhật Jira lúc closeout (mô tả, estimate, worklog) và có báo cáo tuần.
  - **Đề xuất:** thêm vào `jira-workflow` một lệnh "ghi block" chạy ở các mốc lane: triage, duyệt plan, gate xanh,
    Done. Mỗi block ghi mốc, người hoặc agent, bằng chứng (SHA, kết quả gate) và chỉ nối thêm vào comment hoặc mô tả.
    Báo cáo tuần có thêm hai nhóm "chờ người" và "bị chặn".
  - **Lưu ý:** luật này không mâu thuẫn với luật living docs. Ticket là nhật ký nên chỉ nối thêm; tài liệu là trạng thái
    hiện hành nên được sửa tại chỗ.
  - **Ưu tiên:** 1.
- **B2. Hợp đồng chung của agent (slide 11, 28).**
  - **Deck:** đầu vào → làm trong phạm vi → đầu ra kèm bằng chứng. Agent không bao giờ tự duyệt, merge, deploy hay đọc
    secret. Khi chạm cổng, agent dừng, gắn `needs-human`, gom câu hỏi một lượt kèm đề xuất rồi làm việc khác. Việc bỏ
    dở được ghi thành block handoff (đã thử gì, nghi nguyên nhân gì).
  - **Hiện có:** mỗi skill có điểm dừng riêng; brief cho hand có khuôn riêng. Chưa có định dạng chung cho "câu hỏi gom
    một lượt" và "handoff".
  - **Đề xuất:** thêm template `handoff.md`, dùng chung cho `resume-work`, `bug-investigation` và closeout khi việc còn
    dở. Khi dừng ở cổng, agent luôn đưa câu hỏi kèm phương án đề xuất. Nếu repo dùng Jira, gắn nhãn `needs-human`
    (tên nhãn đặt trong config).
  - **Ưu tiên:** 1.

### C. Mức giao việc và vòng tự sửa

- **C1. Chế độ chạy, độc lập với lane (slide 22, 23).**
  - **Deck:** giao hẳn cho agent khi việc rõ, có spec và test. AI đề xuất, người duyệt từng bước khi cần quyết định giữa
    chừng. Người cầm lái khi việc nhiều module, đổi kiến trúc, chạm bảo mật/phân quyền, nghiệp vụ nhiều nhánh, hoặc
    ước lượng từ L trở lên.
  - **Hiện có:** lane cho biết cần những artifact nào, nhưng không nói người tham gia ở mức nào khi thực thi. C1-C9
    chưa có tiêu chí bảo mật hay phân quyền.
  - **Đề xuất:** thêm dòng `CHẾ ĐỘ: tự chạy | duyệt từng bước | người cầm lái` vào khối Triage, gợi ý theo lane và tiêu
    chí. Thêm C10 "chạm bảo mật, phân quyền, dữ liệu nhạy cảm", tối thiểu đẩy lên L2 kèm chế độ duyệt từng bước.
  - **Ưu tiên:** 1.
- **C2. Trần số vòng tự sửa (slide 15, 26).**
  - **Deck:** khi QA fail, ticket tự trả về; agent Dev và agent BA tìm xem lỗi do code hay do spec; agent Dev sửa, agent
    QA kiểm lại. Quá 3 vòng mà chưa pass thì gắn `needs-human`.
  - **Hiện có:** gate đỏ hoặc self-review ra needs-fix thì agent sửa rồi chạy lại, không có giới hạn số vòng.
  - **Đề xuất:** đưa vào `session-closeout` và `self-review`: tối đa 3 vòng gate đỏ → sửa → chạy lại; quá 3 vòng thì
    dừng và báo người theo khuôn handoff (B2). Ở mỗi vòng, ghi rõ nguyên nhân do code hay do spec. Nếu do spec thì đi
    theo luồng CR, không tự sửa SRS.
  - **Ưu tiên:** 1.

### D. Tài liệu và truy vết

- **D1. Quyết định mới vào SRS ngay khi phát sinh (slide 21, 27).**
  - **Deck:** gặp điểm SRS chưa có thì agent dừng, hỏi BA, không đoán. BA xác nhận xong, agent ghi vào SRS và ticket
    cùng lúc. Khi release, agent đối chiếu tài liệu với hệ thống đang chạy thêm một lần.
  - **Hiện có:** câu hỏi mở `OQ-n`; SRS chỉ đổi qua CR (skill `spec-plan`).
  - **Đề xuất:** thêm luật vào `spec-plan`: một `OQ-n` đã được trả lời phải được ghi ngay vào SRS (qua CR nhỏ nếu SRS
    đã duyệt) và vào ticket trong cùng phiên, không dồn tới cuối đợt. Closeout kiểm "không còn OQ đã trả lời mà chưa
    ghi".
  - **Ưu tiên:** 1.
- **D2. Chuỗi PRD → SRS → test case có mã (slide 17, 20).**
  - **Deck:** mỗi mục SRS trỏ về mục PRD sinh ra nó. Test case `TC-05-01` trỏ về `UC-05`. QA viết test case trước khi
    code xong. Khi khách đổi yêu cầu, chuỗi truy vết chỉ ra phần bị ảnh hưởng để báo thời gian và chi phí.
  - **Hiện có:** `dw trace` truy vết FR → task → test tự động (theo tên test). Chưa có loại ID cho test case viết tay,
    chưa có tầng PRD.
  - **Đề xuất:** cho phép khai `TC` trong `[trace] id_types`, quét thêm file test case viết tay (đường dẫn trong
    `[paths]`), và thêm template `test-cases.md`. Báo cáo ảnh hưởng của CR liệt kê thêm các TC bị chạm.
  - **Ưu tiên:** 2.
- **D3. Duyệt thay đổi tài liệu theo lô, chỉ trên phần khác (slide 27, 29).**
  - **Deck:** agent gom các đoạn sửa SRS theo mục (mục nào, trước và sau, ticket nguồn). BA duyệt một lượt mỗi ngày.
    Spec sửa sau khi đã duyệt thành bản mới; người chỉ duyệt lại phần khác nhau.
  - **Hiện có:** CR viết báo cáo ảnh hưởng rồi dừng chờ duyệt, mỗi CR một lần.
  - **Đề xuất:** thêm vào template `cr.md` một bảng "trước / sau / nguồn" theo từng mục, để người duyệt chỉ đọc phần
    khác. Cho phép gộp nhiều thay đổi nhỏ vào một CR khi chúng cùng một mục.
  - **Ưu tiên:** 2.

### E. Áp dụng và kết thúc vòng đời

- **E1. Khôi phục tài liệu cho dự án cũ (slide 32).**
  - **Deck:** khi code cùng dev, agent khám phá luồng xuyên module và hỏi ở những chỗ chưa rõ. Dev xác nhận thì agent
    ghi vào thư mục docs của module. Sau đó BA Document tổng hợp các thư mục này thành SRS bản khôi phục, có người
    duyệt. Chức năng nào đủ SRS và test thì mới bật agent tự chạy cho chức năng đó.
  - **Hiện có:** chỉ có hướng dẫn chép config mẫu (`README.md`). Truy vết trên repo chưa có SRS sẽ báo thiếu hàng loạt.
  - **Đề xuất:** thêm skill `legacy-docs` (hoặc một luật trong `dev-triage`): khi đụng luồng chưa có tài liệu, ghi luồng
    đã được dev xác nhận vào docs của module, kèm nguồn "dev xác nhận ngày ...". Cho `dw trace` một chế độ chỉ kiểm
    các feature đã có SRS.
  - **Ưu tiên:** 2.
- **E2. Release và định nghĩa Done (slide 15, 25, 28).**
  - **Deck:** agent xếp thứ tự release (việc phụ thuộc và rủi ro thấp đi trước). Mỗi task có một merge request kèm bằng
    chứng QA và cách rollback. Người bấm deploy. Task chỉ Done khi production chạy đúng commit đó.
  - **Hiện có:** cổng release chỉ có trên lý thuyết (`docs/ai-dev-workflow.md`); chưa có skill. Done trên Jira dựa vào
    gate xanh.
  - **Đề xuất:** thêm skill `release-prep` (không deploy): lập danh sách thay đổi theo thứ tự, mỗi mục kèm bằng chứng
    gate và cách rollback. Thêm vào config một trường chọn định nghĩa Done: `gate` (mặc định) hoặc `deployed`.
  - **Ưu tiên:** 2.

### Ưu tiên 3: cần hạ tầng, cân nhắc sau

Các điểm sau đòi hỏi tiến trình chạy nền, quyền ghi lên board, hoặc CI chạy test. Plugin hiện không có những thứ đó.

- **Agent tự nhận việc theo cột, chạy đêm, mỗi ticket một worktree riêng** (slide 13, 28). Cần cơ chế chạy theo lịch
  ngoài phiên, ví dụ routine trên cloud, và CI chạy test thật.
- **Giới hạn số merge request đang chờ review**: đủ số thì agent ngừng nhận việc mới (slide 28).
- **Trần chi phí AI theo dự án, đo bằng CodeBurn** (slide 4, 31). Hướng mở rộng: dev-workflow đã tính giờ thật từ
  transcript, có thể tính thêm token.
- **Bản đồ module và CodeGraph để biết sửa đâu ảnh hưởng đâu** (slide 4). Có thể bắt đầu bằng một file bản đồ module
  do repo khai, gắn với A1.
- **Hỗ trợ Codex** (slide 5). Muốn làm thì phải tách luật ra khỏi định dạng skill riêng của Claude Code.

## 4. Không nên chép nguyên

- **Tự động 24/7 khi chưa có CI chạy test.** Agent tự merge request qua đêm chỉ an toàn khi có CI. Repo đích hiện chỉ
  chạy lint trên CI, phần test bị comment (`docs/skill-proposal.md`). Cần có CI trước, rồi mới tới ưu tiên 3.
- **Chi tiết gắn với công cụ.** Linkup, GitLab, Space, các cột To Do/Ready/Test Review là của môi trường trong deck.
  Theo đúng tinh thần của deck ("kit chỉ đọc và đi theo", slide 6), dev-workflow nên đọc tên trạng thái và nhãn từ
  `[jira]` trong config, không định nghĩa cứng.
- **Ba agent theo vai trong một plugin dev.** Phần BA (PRD, SRS, brainstorm) thuộc chuỗi ai4ba
  (`docs/ai-dev-workflow.md`). dev-workflow chỉ nên học các điểm giao giữa hai bên (D1, D2), không gánh luôn vai BA hay QA.
- **Số liệu minh hoạ.** Mã ticket, giờ giấc, "4 MR chờ người" trong deck là ví dụ trong video, không phải số đo.

## 5. Bước tiếp theo đề xuất

- Người dùng chọn các mục ưu tiên 1 sẽ làm: A2, B1, B2, C1, C2, D1.
- Agent lập plan L2 mới ở `docs/plans/` qua skill `spec-plan`. Mỗi mục là một task `T-..` có test, sau đó tăng
  `plugin.json` lên 0.6.0.
- Các mục ưu tiên 2 và 3 giữ lại trong file này làm danh sách tồn đọng. Khi làm mục nào thì xoá mục đó khỏi file và
  dẫn link sang plan.
