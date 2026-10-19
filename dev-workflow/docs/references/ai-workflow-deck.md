# AI Workflow – Quy trình phát triển dự án cùng AI (bản Markdown của deck)

Nguồn: artifact claude.ai <https://claude.ai/artifact/Nz5NTWyc54nhKSfr7wjJQ4> (bản tạo 2026-10-16), nội dung từ video cùng tên, tác giả kiến trúc: Hưng Khánh. Chuyển sang Markdown ngày 2026-10-19; mã ticket, giờ giấc là minh hoạ trong video.

## Tóm tắt

- **Thông điệp chính:** một bộ luật, một quy trình, cả team cùng AI. Kit AI Workflow (một nguồn duy nhất trên GitLab) chứa luật, skill, hook cho mọi người và mọi AI agent (Claude Code + Codex); việc của người và AI ghi chung một board Linkup qua MCP.
- **Phần II:** 3 agent BA/Dev/QA, mỗi agent do một vai trò quản lý, tự nhận việc ở một cột trên board, chạy cả ngày lẫn đêm; người giữ các cổng quyết định (duyệt spec, merge, deploy). Agent không tự duyệt, không merge, không deploy, không đọc secret.
- **5 phần của deck:** Mở đầu (5 vấn đề khi các team cùng dùng AI) → Phần I (workflow chung) → Phần II (AI agent theo vòng đời dự án) → Ví dụ thực tế (một ngày trên board Linkup) → Tổng kết và áp dụng cho dự án cũ.
- **Số liệu chính:** 4 nhóm tính năng kit; 2 mức áp dụng (kit trước, agent sau); 3 agent; 11 chặng vòng đời dự án; 9 bước bản đồ giai đoạn phát triển; 3 mức giao việc; tối đa 3 vòng tự sửa trước khi gắn `needs-human`; 7 cột board (To Do → Done).
- **Truy vết tài liệu:** PRD → SRS → test case → ticket → merge request → bằng chứng QA; yêu cầu đổi thì chuỗi truy vết chỉ ra phần bị ảnh hưởng.
- **Dự án cũ:** khôi phục tài liệu từ code trước (dev xác nhận, BA Document tổng hợp SRS); chức năng nào đủ SRS và test mới bật agent tự động.
- **Câu chốt:** AI tăng tốc phần làm. Quy trình giữ phần đúng. Con người giữ phần quyết.

## Mục lục

| Phần | Slide |
|---|---|
| Mở đầu: những vấn đề khi các team cùng dùng AI | 1–2 |
| Phần I: một workflow chung cho các team trong dự án | 3–7 |
| Phần II: AI agent tự động theo vòng đời dự án | 8–23 |
| Ví dụ thực tế: một ngày trên board Linkup | 24–29 |
| Tổng kết và áp dụng cho dự án cũ | 30–33 |

## Mở đầu: những vấn đề khi các team cùng dùng AI

### 1. Một bộ luật. Một quy trình. Cả team cùng AI.

- Quy trình phát triển toàn team với AI, gồm hai phần: một workflow chung để mọi người và mọi AI agent theo cùng quy trình, và AI tự động trong công việc hằng ngày.
- Công cụ: Claude Code + Codex; Linkup · GitLab. Tác giả kiến trúc: Hưng Khánh.
- Sơ đồ: AI Workflow ở giữa, nối với Dev A (Claude), Dev B (Codex), AI agent (24/7), Reviewer (duyệt MR), PM (Linkup), Team khác (nhân rộng).

> **Lời thoại:** Video gồm hai phần: một workflow chung cho cả team dùng AI, và AI tự động trong công việc hằng ngày. Quy trình đã được nghiên cứu và chạy thật ở quy mô một người; áp dụng cho toàn team, rồi nhân rộng sang các team khác. Công cụ: Claude Code và Codex, chạy trên macOS, Windows, Linux; bản đồ module; Linkup và GitLab.

### 2. Năm vấn đề khi các team cùng dùng AI

1. **Phát quy trình thủ công:** gửi plugin, framework cho từng người tự cài. Không biết ai đã cài, dùng có đúng không.
2. **Phải đi đôn đốc:** mỗi lần có quy trình mới: phổ biến xong còn phải nhắc từng người cài vào dự án.
3. **Luật chung không ai giữ:** đồng bộ việc lên Linkup, format commit… mỗi người làm một kiểu.
4. **Kỹ năng AI chênh lệch:** người dùng tốt, người chưa; cách làm hay khó chia sẻ cho cả nhóm.
5. **Mỗi người một kiểu:** mỗi người một công cụ, một prompt, nên kết quả phụ thuộc người dùng AI.

**Câu hỏi đặt ra:** Làm sao quản trị được cả con người lẫn AI: thấy việc đang ở đâu, AI đã làm gì, việc nào AI tự làm, và kết quả có đúng không?

> **Lời thoại:** Hiện quy trình AI được phát thủ công: gửi cho mỗi người các plugin, framework cần cài, rồi ai nấy tự cài. Không biết ai đã cài, dùng có đúng không. Mỗi lần có quy trình mới thì phổ biến xong còn phải đi nhắc từng người. Luật chung như đồng bộ công việc lên Linkup hay format commit thống nhất chưa có ai giữ, mỗi người làm một kiểu. Kỹ năng AI chênh lệch, và mỗi người một công cụ, một prompt nên kết quả phụ thuộc người dùng. Câu hỏi đặt ra là làm sao quản trị được cả con người lẫn AI: nhìn thấy việc nào đang ở đâu, theo dõi AI đã làm gì, kiểm soát việc nào AI tự làm, và kiểm tra kết quả có đúng không. Vì vậy cần một quy trình chung, làm luật để mọi người cùng đi theo.

## Phần I: một workflow chung cho các team trong dự án

### 3. Một workflow chung cho các team trong dự án

Mọi thành viên, mọi AI agent theo cùng một quy trình, quản trị được cả người lẫn AI.

> **Lời thoại:** Phần một: các team trong dự án dùng AI theo một workflow chung, quản trị được cả thành viên lẫn AI agent.

### 4. Bên trong kit AI Workflow: bốn nhóm tính năng

| Nhóm | Tính năng |
|---|---|
| 1. Luật chung | Việc lớn đi đúng quy trình (có người duyệt) · Luật bất biến (không ai được nới) · Luật riêng theo module (riêng thắng chung) |
| 2. Hook tự kiểm | Hook tự cập nhật kit (mặc định bật) · Hook kiểm tra khác (team tự bật, tắt) · Thêm hook mới (không đổi cách làm) |
| 3. Mọi việc trên Linkup | Tiến độ tự cập nhật (người và AI chung board) · Tạo task từ ghi chú (không tạo trùng) · Điều tra bug (có bằng chứng) |
| 4. Hiểu hệ thống, đo được | Bản đồ module (ai gọi ai) · CodeGraph (sửa đâu ảnh hưởng đâu) · CodeBurn (chi phí AI mỗi dự án) |

> **Lời thoại:** Nhóm một, luật chung: việc lớn đi đúng quy trình làm rõ, plan, duyệt, làm, kiểm tra, merge request, có người duyệt; luật bất biến không ai được nới; luật riêng theo module, riêng thắng chung. Nhóm hai, hook tự kiểm: mặc định có hook tự cập nhật kit; các hook kiểm tra khác thì mỗi team tự bật hay tắt. Thêm hay bớt hook không làm đổi cách làm. Nhóm ba, mọi việc trên Linkup: tiến độ tự cập nhật, người và AI chung một board; tạo task từ ghi chú mà không tạo trùng; điều tra bug có bằng chứng. Nhóm bốn, hiểu hệ thống và đo được: bản đồ module, CodeGraph để biết sửa đâu ảnh hưởng đâu, và CodeBurn đo mức dùng AI. Luật nằm trong kit, nên ai dùng AI cũng tuân theo cùng một workflow. Mỗi team bật, tắt tùy ý.

### 5. Một người công khai quy trình, cả team cùng theo

Luồng: Chủ quy trình (người; đề xuất, duyệt thay đổi của kit) → Merge request → Kit AI Workflow → Mọi máy tự nhận bản mới.

- **Merge request** `!57 · thêm luật migration`: `+ Sửa migration → hỏi tech lead`; Tech lead duyệt → merge vào kit.
- **Kit AI Workflow** `v0.8.1` (GitLab · một nguồn duy nhất), luật xếp tầng: Luật chung · core (áp cho mọi người, mọi team) → Pack theo nhóm, vị trí → Luật riêng của module → Cá nhân (riêng thắng chung, trừ luật bất biến). Kèm: skill, hook, bản đồ module.
- **Mọi máy tự nhận bản mới:** Dev A (Claude Code), Dev B (Codex), BA (Claude Code), QA (Codex), Team khác (pack riêng, cùng core).

> **Lời thoại:** Kit AI Workflow nằm trên GitLab, là một nguồn duy nhất. Luật xếp theo tầng: luật chung (core) áp cho mọi người, mọi team; pack theo nhóm, vị trí; luật riêng của module; và cấu hình cá nhân, riêng thắng chung, trừ luật bất biến. Ví dụ: chủ quy trình muốn thêm một luật “sửa file migration phải hỏi tech lead”. Thay đổi đi qua merge request, có người review rồi mới merge. Merge xong, mọi máy (Dev A dùng Claude Code, Dev B dùng Codex, BA, QA, team khác) tự nhận bản kit mới ở lần dùng AI tiếp theo; không ai phải cài lại hay chép prompt. Ngay sau đó, agent Codex trên máy Dev B định sửa file migration và dừng lại hỏi tech lead, đúng luật vừa thêm. Mỗi phiên trên mọi máy đều nhận cùng một bộ luật, skill và các hook mà team đã bật. Công khai một lần, cả team cùng theo.

### 6. Mọi người, mọi agent ghi việc lên Linkup qua MCP

1. Kit có sẵn MCP Linkup, cấu hình cho cả Claude Code lẫn Codex.
2. Mỗi người đăng nhập một lần, bằng OAuth hoặc token được cấp.
3. Agent của ai cũng ghi tiến độ theo một mẫu: block nối vào mô tả ticket, commit có mã việc.
4. Mỗi team, dự án một Space riêng: cột nào, ai được chuyển do team đặt; kit chỉ đọc và đi theo.

Ví dụ mô tả ticket LK-123 “Lọc briefing theo ngày”: `[spec #1]` Agent BA – spec nháp · TC 1–5; `[duyệt]` Dev A – task-fetch · chế độ: agent tự động; `[merge request]` Agent Dev – plan 4 bước · test xanh.

> **Lời thoại:** Muốn dùng kit hiệu quả thì phải kết nối kit với Linkup qua MCP. Có kết nối này, quy trình mới thật sự chạy: agent đọc ticket, ghi tiến độ, và cả team cùng nhìn một nơi. Cài kit là MCP Linkup được cấu hình sẵn cho cả Claude Code lẫn Codex. Mỗi người đăng nhập một lần, bằng OAuth hoặc token được cấp. Mỗi team, mỗi dự án có một Space riêng; trạng thái đi theo Space đó. Có những cột nào, ai được chuyển là do team tự đặt; kit không định nghĩa cứng, chỉ đọc và đi theo. Agent của ai cũng ghi tiến độ theo cùng một mẫu: block nối vào mô tả ticket, commit có mã việc. Nhờ vậy việc của người hay của AI đều hiện trên cùng một Kanban, cập nhật ngay trong lúc làm, không dồn tới cuối ngày.

### 7. Cài xong, mỗi thành viên nhận được gì

Cài kit, kết nối Linkup, mở công cụ AI đang dùng trong repo dự án. Không cần nhớ lệnh.

| Vai | Nhận được |
|---|---|
| Dev – Giao việc bằng một câu | “làm LK-123” · Agent đã biết luật team và module · Code theo test · Commit tự gắn mã việc |
| BA · QA – Cùng một mẫu làm việc | Soạn spec theo mẫu chung · Viết test case theo một chuẩn · Dùng skill có sẵn, không chép prompt |
| Tự kiểm – Luật đi theo từng phiên | Luật nạp sẵn mỗi phiên · Hook tự kiểm: team tự bật, tắt · Tiến độ tự ghi lên Linkup |
| PM · Lead – Nhìn một board là đủ | AI đang làm gì, tới đâu · Việc của người và AI cùng một Kanban · Luật đổi: mọi máy tự nhận |

Phổ biến một lần · không phải đôn đốc từng người.

> **Lời thoại:** Cài kit xong, mỗi thành viên nhận được gì? Không cần nhớ lệnh nào: chỉ cần mở công cụ AI mình đang dùng ngay trong repo dự án. Dev giao việc bằng một câu như “làm LK-123”; agent đã biết luật team và module, code theo test, commit tự gắn mã việc. BA và QA dùng cùng bộ luật và skill: soạn spec, viết test case theo mẫu chung, không phải tự chép prompt. Luật nạp sẵn mỗi phiên, hook tự kiểm, tiến độ tự ghi lên Linkup. PM và Lead nhìn một board là đủ. Luật đổi thì mọi máy tự nhận bản mới. Phổ biến một lần, không phải đi đôn đốc từng người.

## Phần II: AI agent tự động theo vòng đời dự án

### 8. Quy trình các team trong vòng đời dự án

AI agent tự động trong công việc hằng ngày: chạy liên tục để phát triển liên tục.

> **Lời thoại:** Phần hai: các team làm việc thế nào trong suốt vòng đời phát triển dự án, và AI agent tự động trong công việc hằng ngày, chạy liên tục để phát triển liên tục.

### 9. Đã có workflow chung, sao còn cần agent tự động?

- **Hiện nay:** việc chờ người đẩy từng bước; hết giờ, AI đứng yên. Giao song song cho nhiều agent thì người phải ngồi trông từng phiên: Agent 1 · chat (đang chạy gì?), Agent 2 · terminal (chờ trả lời?), Agent 3 · IDE (xong chưa, lỗi ở đâu?).
- **Cần:** agent tự nhận việc trên board. Người chỉ giữ các cổng quyết định.

> **Lời thoại:** Có workflow chung rồi, nhưng việc vẫn chờ người đẩy từng bước; hết giờ làm thì AI cũng đứng yên. Giao song song cho nhiều agent thì người lại phải ngồi trông từng phiên: agent nào đang chạy, agent nào chờ trả lời, xong chưa, lỗi ở đâu. Cần một cách để agent tự nhận việc trên board, còn người chỉ giữ các cổng quyết định.

### 10. Ba agent, mỗi agent do một vai trò quản lý

| Agent | Việc | Nhận ở cột |
|---|---|---|
| Agent BA · BA quản lý – Làm rõ, soạn tài liệu | Làm rõ yêu cầu, soạn spec · Viết PRD, SRS · Giữ tài liệu khớp thực tế | To Do |
| Agent Dev · Dev quản lý – Code theo spec | Nhận việc đã có spec · Lập plan, code, chạy test · Mở merge request | Ready |
| Agent QA · QA quản lý – Kiểm có bằng chứng | Viết test case từ SRS · Kiểm trên trình duyệt thật · Ảnh chụp, log làm bằng chứng | Test Review |

- Không có BA hay QA? Chỉ cần skill của agent đó: agent chạy độc lập, người chỉ duyệt.
- Agent nào cũng không tự duyệt, không merge, không deploy.

> **Lời thoại:** Ai làm việc gì? Có ba agent, mỗi agent do một vai trò quản lý. Agent BA do BA quản lý: làm rõ yêu cầu, soạn spec, viết PRD, SRS và giữ tài liệu khớp thực tế. Agent Dev do Dev quản lý: nhận việc đã có spec, lập plan, code, chạy test và mở merge request. Agent QA do QA quản lý: viết test case từ SRS, kiểm trên trình duyệt thật và có bằng chứng. Dự án không có BA hay QA vẫn chạy được, chỉ cần có skill của agent đó: agent chạy độc lập, người chỉ duyệt. Agent nào cũng không tự duyệt, không merge, không deploy.

### 11. Mọi agent theo cùng một hợp đồng

Mỗi agent giữ một đoạn của luồng, tự nhận việc trên board, chạy song song cả ngày lẫn đêm.

1. **Đầu vào:** chỉ nhận ticket đúng cột, đủ điều kiện, theo thứ tự ưu tiên.
2. **Làm:** trong phạm vi skill của mình.
3. **Đầu ra:** chuyển trạng thái và ghi một block vào ticket.
4. **Bằng chứng:** mã commit, kết quả test, ảnh chụp, log.

- **Không bao giờ:** tự duyệt · merge · deploy · đọc secret.
- **Chạm cổng:** dừng, gắn `needs-human`, làm việc khác.

> **Lời thoại:** Vì sao cần agent? Để không ai phải đẩy từng bước. Mỗi agent giữ một đoạn của luồng, tự nhận việc trên board, chạy song song cả ngày lẫn đêm. Mọi agent theo cùng một hợp đồng: chỉ nhận ticket đúng cột, đủ điều kiện, theo thứ tự ưu tiên; làm trong phạm vi skill của mình; xong thì chuyển trạng thái và ghi một block vào ticket. Đầu ra luôn kèm bằng chứng kiểm được: mã commit, kết quả test, ảnh chụp, log. Agent không tự duyệt, không merge, không deploy, không đọc secret. Chạm cổng thì dừng và hỏi người.

### 12. Hai mức áp dụng: kit trước, agent sau

- **Mức 1 · bước đầu tiên – Chỉ dùng kit, chưa bật agent:** thành viên tự làm cùng AI trong phiên của mình, ví dụ “làm LK-123”; kit tự đổi trạng thái ticket, ghi block tiến độ vào mô tả; PM nhìn board là thấy: công việc đã minh bạch.
- **Mức 2 · khi team sẵn sàng – Bật agent tự động:** kit có sẵn cấu hình agent, bật lên là chạy; mỗi agent giữ một cột trên Linkup; agent chạy cả ngoài giờ, người duyệt ở các cổng.

> **Lời thoại:** Chưa bật agent, chỉ dùng kit, công việc đã minh bạch. Thành viên tự làm cùng AI trong phiên của mình, ví dụ “làm LK-123”; kit tự đổi trạng thái ticket và ghi block tiến độ vào mô tả; PM nhìn board là thấy. Đây là bước đầu tiên. Agent tự động là bước tiếp theo, khi team đã sẵn sàng: kit đã có sẵn cấu hình agent tự động, muốn dùng thì bật lên.

### 13. Mỗi agent giữ một cột trên board

| To Do | Ready | Đang làm | Dev Review | Test Review | Ready to Deploy |
|---|---|---|---|---|---|
| Agent BA nhận: LK-140 (cần spec) | Agent Dev nhận: LK-123 (đủ spec); LK-130 (human dev: agent bỏ qua) | | | Agent QA nhận: LK-118 (đã lên dev) | |

- **Đưa cho agent:** spec hoặc SRS · test case (nếu có) · nhãn trên ticket · luật của module.
- **Nhận lại từ agent:** block kết quả trong ticket · merge request kèm kết quả test · bằng chứng kiểm thử.

> **Lời thoại:** Vì sao agent tự chạy được, và cần đưa cho nó những gì? Mỗi agent giữ một cột trên Linkup. Agent BA quét To Do, tìm ticket còn cần spec. Agent Dev chỉ nhận ticket ở Ready, tức là đã có spec chi tiết. Agent QA chỉ nhận ticket ở Test Review. Ticket gắn nhãn human dev thì agent không đụng tới, và lúc nào cũng có thể làm thủ công. Trước khi bật, cần đưa cho agent: spec hoặc SRS, test case nếu có, nhãn trên ticket và luật của module. Đầu ra mong muốn: block kết quả trong ticket, merge request kèm kết quả test, bằng chứng kiểm thử để người đọc và duyệt.

### 14. Vòng đời dự án: AI tham gia ở đâu

1\. Ý tưởng khách (PO) → 2. Khám phá (BA) → 3. PRD (BA) → 4. SRS (BA) → 5. Chia đầu mục (BA · PM) → 6. PM phân luồng (PM) → 7. Viết test case (QA) → 8. Phát triển (Dev) → 9. Kiểm thử (QA) → 10. Deploy, bàn giao (PO · Tech Lead) → 11. Bảo trì, nâng cấp (Cả team) → quay lại vòng đầu.

Ở mỗi chặng, AI soạn và làm phần lặp lại; con người duyệt ở cổng.

> **Lời thoại:** Nhìn bức tranh lớn: AI tham gia vào những chặng nào của một dự án. Từ ý tưởng của khách, BA khám phá và chốt nghiệp vụ, rồi ra PRD và SRS. Sau đó chia đầu mục, PM phân luồng. QA viết test case song song với dev phát triển. Tiếp theo là kiểm thử, deploy và bàn giao, rồi bảo trì, nâng cấp, quay lại vòng đầu. Ở mỗi chặng, AI soạn và làm phần lặp lại, con người duyệt ở cổng.

### 15. Ai làm gì, ở bước nào, ai gọi ai

Chú giải: Người · Skill người gọi · Agent.

1\. Người: Nêu ý tưởng (PM, PO) → 2. Skill: `create-task` (ghi vào To Do) → 3. Agent: Agent BA (làm rõ, soạn spec nháp) → 4. Người: Dev duyệt spec (`task-fetch`, chọn chế độ chạy) → 5. Agent: Agent Dev (plan, code, test, mở MR) → 6. Người: Review, merge (lên môi trường dev) → 7. Agent: Agent QA (kiểm trên dev) → 8. Người: QA người (xác nhận, Ready to Deploy) → 9. Skill: `release` (Tech Lead gọi, lên production).

**Khi lỗi:** ticket tự trả về, agent tự sửa; quá 3 vòng mới về người.

> **Lời thoại:** Đây là bản đồ của giai đoạn phát triển: ai làm gì, ở bước nào, ai gọi ai. Sơ đồ bắt đầu khi dự án đã có tài liệu và dev vào làm, kết thúc khi bàn giao. Các tác nhân gồm: con người (PM, PO, Dev, BA, QA); các skill người gọi như create-task, task-fetch; ba agent (BA do BA quản lý, Dev do Dev quản lý, QA do QA quản lý); và skill release do Tech Lead gọi. Một ticket: ý tưởng được ghi vào To Do, agent BA soạn spec nháp. Dev dùng task-fetch lấy ticket từ To Do, đọc spec xem đã rõ và đủ cho agent chưa. Đủ rõ thì dev duyệt spec và chọn agent tự động, ticket sang Ready, gắn cho agent Dev. Cần quyết định giữa chừng thì dev đổi sang human in the loop. Agent Dev lập plan, code, chạy toàn bộ test rồi mở merge request. Người review và merge lên môi trường dev. Agent QA và QA người kiểm; đạt thì sang Ready to Deploy, rồi Tech Lead release lên production. Fail thì ticket tự trả về: agent Dev và agent BA cùng tìm nguyên nhân, agent Dev sửa luôn, agent QA kiểm lại. Qua ba vòng vẫn chưa pass mới trả về người.

### 16. Team BA: từ nghiệp vụ tới ticket rõ ràng

Luồng: BA + khách: Chốt nghiệp vụ (buổi họp, email, bản mẫu) → Agent BA soạn: PRD (người duyệt · lưu Linkup) → BA + agent: SRS (người duyệt · lưu Linkup) → Agent chia: Đầu mục lớn (người đồng ý → ticket trên board).

- **Board Khám phá của BA trên Linkup (chỉ dùng nội bộ):** Yêu cầu thô → Làm rõ cùng AI → Bản mẫu → Chờ khách xác nhận → PRD đã chốt → Tách thành ticket.
- BA Brainstorming đặt câu hỏi, nêu giả định, viết user story. BA Document viết PRD theo mẫu chung, có phiên bản.
- Khách xác nhận là một cổng: ghi vào ticket kèm email hay biên bản. Sau đó, đổi gì cũng thành yêu cầu thay đổi.

> **Lời thoại:** Team BA biến yêu cầu của khách thành ticket rõ ràng, có người duyệt ở mỗi bước. BA làm việc với khách, chốt nghiệp vụ. Agent BA soạn PRD, người duyệt, lưu trên Linkup. Từ PRD, BA cùng agent soạn SRS, người duyệt, lưu trên Linkup. Từ SRS, agent chia thành các đầu mục lớn; người duyệt bấm đồng ý thì ticket được tạo trên board. Đầu ra của team BA là PRD, SRS và danh sách ticket đã duyệt. Trước khi có ticket, BA làm việc trực tiếp với khách; quá trình này vẫn được theo dõi trên Linkup, trong không gian riêng của BA, để người quản lý nắm được BA đang làm tới đâu. Yêu cầu thô từ cuộc họp hay email được ghi thành thẻ. BA dùng skill BA Brainstorming để đặt câu hỏi, nêu giả định, viết user story. BA dựng bản mẫu bằng công cụ mình chọn, Figma hay HTML, có AI hỗ trợ, rồi đưa khách xem. Linkup chỉ dùng nội bộ, khách làm việc với BA. Khách xác nhận là một cổng: xác nhận được ghi vào ticket kèm bằng chứng như email hay biên bản. Sau đó đổi gì cũng phải thành yêu cầu thay đổi. Bản đã chốt được skill BA Document viết thành tài liệu PRD theo mẫu chung, có phiên bản. Mẫu và luật nằm trong kit nên BA nào cũng làm giống nhau.

### 17. PRD → SRS → test case: một chuỗi truy vết

| Tài liệu | Ví dụ minh hoạ | Trỏ về |
|---|---|---|
| PRD (khách đã xác nhận) | 4 · Tìm kiếm và lọc; 4.3 · Lưu bộ lọc yêu thích; 5 · Xuất và thông báo | BRF-01 · email khách |
| SRS (BA Document soạn · BA duyệt) | UC-05 · Lưu bộ lọc yêu thích: luồng chính, luồng phụ, lỗi; quy tắc: tối đa 10 bộ lọc mỗi người | PRD 4.3 |
| Bộ test case (QA người viết cùng agent QA) | TC-05-01 Lưu một bộ lọc mới; TC-05-02 Trùng tên thì báo lỗi; TC-05-03 Quá 10 bộ lọc | SRS UC-05 |

**Truy vết:** PRD 4.3 → SRS UC-05 → TC-05-01…04 → ticket LK-121 → merge request → bằng chứng QA.

Khách đổi yêu cầu (giới hạn 10 → 20 bộ lọc)? Chuỗi truy vết chỉ ra phần bị ảnh hưởng, để BA báo thời gian, chi phí trước khi nhận.

> **Lời thoại:** PRD là tầng trên cùng. Từ PRD đã được khách xác nhận, skill BA Document soạn tiếp tài liệu SRS: tình huống sử dụng, luồng xử lý, quy tắc nghiệp vụ, dữ liệu và ràng buộc. BA người đọc và duyệt SRS. Mỗi mục SRS có mã riêng và trỏ ngược về mục PRD sinh ra nó. Song song, QA người cùng agent QA viết bộ test case từ SRS; mỗi test case gắn mã, chỉ rõ mục SRS nó kiểm, dữ liệu thử và các cỡ màn hình. Ba tài liệu nối với nhau thành một chuỗi truy vết: mục PRD, mục SRS, test case, rồi tới ticket. Khách đổi yêu cầu thì chuỗi truy vết chỉ ra phần bị ảnh hưởng, để BA báo thời gian và chi phí trước khi nhận. Mẫu tài liệu và cách đặt mã nằm trong kit; team BA sở hữu mẫu và sửa qua merge request.

### 18. PM quyết việc nào trước, ai làm: agent hay người

- **Skill tạo task:** đọc PRD, SRS, test case · tách epic, story rồi task nhỏ · mỗi task trỏ về mục SRS và test case, kèm ước lượng · task đã có thì không tạo trùng · người duyệt bảng nháp xong mới ghi lên Linkup.

| Luồng | Ticket |
|---|---|
| A – tài khoản | LK-201 Đăng nhập (agent tự chạy) · LK-205 Phân quyền (human dev) |
| B – briefing | LK-202 Lọc briefing (agent tự chạy) · LK-204 Xuất báo cáo (agent tự chạy) |
| C – dữ liệu | LK-203 Đổi cấu trúc dữ liệu (human dev) · LK-206 Thông báo email (agent tự chạy) |

PM thống nhất cùng Tech Lead và người phụ trách chức năng, rồi gắn nhãn: việc nhỏ, rõ → agent tự chạy; việc lớn, khó → human dev.

> **Lời thoại:** Có PRD, SRS và bộ test case rồi thì chia việc. Skill tạo task Linkup đọc các tài liệu đó, tách thành epic, story rồi task nhỏ. Mỗi task trỏ về mục SRS và test case của nó, kèm ước lượng. Agent đưa ra bảng nháp; người nhận ước lượng, vị trí trong cây; task nào đã có thì không tạo trùng. Người duyệt xong mới ghi lên Linkup. Mỗi task được gắn chế độ: việc nhỏ, rõ ràng thì để agent tự chạy; việc lớn, khó thì giao human dev. Task đổ sang board của team phát triển. Từ đây, luồng làm việc hằng ngày bắt đầu: PM quyết định việc nào làm trước, ai làm, agent hay người. PM duyệt danh sách đầu mục, chia luồng theo nghiệp vụ và độ ưu tiên. Ticket nào giao agent, ticket nào giao người: PM thống nhất cùng Tech Lead và người phụ trách chức năng đó, rồi gắn nhãn agent tự chạy hoặc human dev.

### 19. Team Dev: từ ticket chưa rõ tới code đã merge

Agent Dev làm phần code. Dev giữ hai cổng: duyệt spec và review merge request.

Luồng: To Do (Agent BA soạn spec nháp) → **Cổng 1 · Duyệt spec** (Dev đọc bằng `task-fetch`; đủ rõ: chọn agent tự động, chuyển Ready; chưa rõ: BA hoàn thiện thêm) → Ready → code · test (Agent Dev nhận việc, lập plan, code, chạy toàn bộ test, mở merge request) → **Cổng 2 · Review MR** (người review và merge lên môi trường dev) → Test Review (ticket sang QA kiểm thử).

Cần quyết định giữa chừng? Dev đổi ticket sang human in the loop: agent đề xuất, người duyệt từng bước.

> **Lời thoại:** Team Dev đưa một ticket từ chưa rõ tới code đã merge, mà không phải đẩy từng bước. Ở team Dev, agent Dev làm phần code, còn Dev giữ hai cổng: duyệt spec và review merge request. Ticket ở To Do: agent BA soạn spec nháp. Dev dùng task-fetch đọc và duyệt: đủ rõ thì chọn agent tự động và chuyển Ready; chưa rõ thì BA hoàn thiện thêm. Agent Dev nhận việc, lập plan, code, chạy toàn bộ test rồi mở merge request. Người review và merge lên môi trường dev. Ticket sang Test Review.

### 20. Team QA: test case sớm, kiểm có bằng chứng

- **Trước khi code xong – Viết test case từ SRS:** agent chia thành các ticket viết test case theo chức năng · Agent QA nhận từng ticket, viết test case, cập nhật tài liệu test case chung · ghi kết quả vào ticket; QA người duyệt · quản lý theo dõi tiến độ ngay trên Kanban.
- **Trước khi lên production – Kiểm trên môi trường dev:** ticket ở Test Review: đã lên môi trường dev · Agent QA kiểm theo SRS và bộ test case · đạt: ảnh chụp, log làm bằng chứng → Ready to Deploy · lỗi: tự trả về để sửa, tối đa 3 vòng.

Không có test case vẫn kiểm được theo SRS; có test case thì kết quả chính xác hơn.

> **Lời thoại:** Team QA có test case sẵn trước khi code xong, để kiểm thử nhanh và chính xác. Đầu vào là SRS. Agent chia thành các ticket viết test case theo chức năng, người duyệt. Agent QA nhận từng ticket, viết test case, cập nhật vào tài liệu test case chung và ghi kết quả vào ticket. QA người duyệt; quản lý theo dõi tiến độ ngay trên Kanban. Kiểm thử: mọi tính năng được kiểm trên môi trường dev, có bằng chứng trước khi lên production. Agent QA kiểm trên môi trường dev dựa vào SRS và bộ test case. Không có test case vẫn kiểm được, nhưng có thì kết quả chính xác hơn. Đạt thì sang Ready to Deploy. Lỗi thì tự động trả về để sửa, tối đa ba vòng.

### 21. Tài liệu đồng bộ ngay trong lúc phát triển

Luồng: Đang làm: gặp điểm chưa có trong SRS (quyết định mới phát sinh) → Agent: dừng lại, hỏi BA (không tự đoán) → BA: xác nhận (một lần) → Agent BA: ghi vào SRS và ticket (cùng một lúc) → Cả team: làm theo bản mới (Dev, QA, agent).

Tài liệu cập nhật ngay trong lúc làm, không dồn tới cuối đợt.

> **Lời thoại:** Tài liệu dự án: quyết định mới phát sinh trong lúc phát triển cũng phải vào SRS ngay. Đang làm mà gặp điểm chưa có trong SRS, agent dừng lại và hỏi BA, không tự đoán. BA xác nhận. Agent BA ghi ngay quyết định đó vào SRS và vào ticket cùng một lúc. Dev, QA và các agent làm tiếp theo bản tài liệu mới, không phải chờ tới cuối đợt mới cập nhật.

### 22. Ba mức giao việc

| Mức | Khi nào | Ví dụ | Nhãn |
|---|---|---|---|
| 1 – Giao hẳn cho agent | Việc rõ ràng; có spec, có test | Lọc danh sách, sửa giao diện | agent tự chạy |
| 2 – AI đề xuất, người duyệt từng bước | Cần quyết định giữa chừng; người duyệt mỗi bước | Đổi luồng nghiệp vụ | người duyệt từng bước |
| 3 – Human dev cầm lái | Việc lớn, khó; chạm migration, kiến trúc; AI chỉ hỗ trợ | – | human dev |

> **Lời thoại:** Giao cho AI tới đâu là an toàn? Việc rõ ràng, có spec, có test: giao hẳn cho agent. Việc cần quyết định giữa chừng: AI đề xuất, người duyệt từng bước. Việc lớn, khó, chạm migration hay kiến trúc: human dev cầm lái, AI chỉ hỗ trợ.

### 23. Việc lớn, khó: human dev cầm lái, agent hỗ trợ

**Khi nào giao human dev?** Đụng nhiều module hoặc đổi kiến trúc · Bảo mật, phân quyền, dữ liệu nhạy cảm · Nghiệp vụ phức tạp, nhiều nhánh xử lý · Ước lượng lớn (L trở lên).

Dev B · phiên làm việc LK-140 (đổi phân quyền):

| Bước | Agent | Dev B |
|---|---|---|
| Nhận việc | Kit ghi ticket đang làm, nạp luật module | Xác nhận phạm vi |
| Plan | Soạn plan 3 bước | Sửa 2 điểm, tech lead xem cùng |
| Bước 1/3 | Thực thi, chạy test | Chọn duyệt từng bước |
| Bước 2/3 | Thực thi, chạy test | Tự code lại một chỗ |

Dùng AI nhiều hay ít là quyền của dev. Vẫn đúng quy trình kit: block, test, review, mã việc.

> **Lời thoại:** Không phải việc nào cũng giao hết cho AI. Đụng nhiều module, đổi kiến trúc, bảo mật, nghiệp vụ phức tạp: những việc này giao cho human dev. Agent BA đề xuất chế độ; người duyệt spec gắn nhãn khi chuyển Ready; Tech Lead được đổi nhãn; dev được nhận việc mình muốn trước khi agent nhận. Agent Dev thấy nhãn human dev thì không nhận. Human dev nghĩa là dev cầm lái: dùng AI nhiều hay ít là quyền của dev. Với LK-140, đổi cơ chế phân quyền, Dev B chọn để agent soạn plan rồi duyệt từng bước. Vẫn đúng quy trình của kit: block trên ticket, test, review, mã việc, rồi QA kiểm như mọi việc khác. Việc khó không bị phó mặc cho AI.

## Ví dụ thực tế: một ngày trên board Linkup

### 24. Ví dụ thực tế: một ngày trên board

LK-123 đi từ ý tưởng tới production, rồi cả một ngày với nhiều ticket chạy cùng lúc.

> **Lời thoại:** Giờ xem ví dụ thực tế. Trước hết là một ticket đi trọn vòng, rồi tới cả một ngày trên board với nhiều ticket chạy cùng lúc. Các mã ticket, giờ giấc trong phần này là ví dụ minh hoạ trong video.

### 25. LK-123 “Lọc briefing theo ngày” đi trọn vòng

Cột: To Do → Ready → In Progress → Dev Review → Test Review → Ready to Deploy → Done.

| Block trong ticket | Nội dung | Ai làm |
|---|---|---|
| `[spec #1]` | Spec nháp · TC 1–5 | Agent BA |
| `[duyệt]` | task-fetch · chế độ: agent tự động | Dev A |
| `[merge request]` | Plan 4 bước · test xanh | Agent Dev |
| `[tích hợp]` | Đã merge · tự kiểm trên dev đạt | Reviewer · Agent Dev |
| `[QA đạt]` | TC 1–5 × 3 cỡ màn hình · ảnh chụp | Agent QA |
| `[release]` | Production chạy đúng commit | Người deploy |

Mỗi bước để lại một block trong ticket: ai mở ra cũng đọc được cả hành trình.

> **Lời thoại:** Một ticket đi trọn vòng: LK-123, lọc briefing theo ngày. PO ghi ý tưởng bằng create-task, ticket vào To Do. Agent BA soạn spec nháp và ghi vào ticket. Dev dùng task-fetch đọc spec, thấy đủ rõ nên duyệt và chọn agent tự động; ticket sang Ready. Agent Dev nhận việc, lập plan, code, chạy toàn bộ test rồi mở merge request; ticket sang Dev Review. Reviewer đọc và merge lên môi trường dev. Agent Dev tự kiểm trên dev rồi chuyển sang Test Review. Agent QA kiểm theo SRS và test case trên ba cỡ màn hình, có ảnh chụp làm bằng chứng. Đạt thì sang Ready to Deploy. Phiên release: người bấm deploy; production chạy đúng commit thì ticket mới Done. Mỗi bước đều để lại một block trong ticket, nên ai mở ra cũng đọc được cả hành trình.

### 26. Lỗi thì tự sửa, không chờ người

Luồng: 1 · Agent QA: kiểm, thấy lỗi (ghi bằng chứng lỗi, tự trả ticket về) → 2 · Agent Dev + Agent BA: tìm nguyên nhân (lỗi do code, hay do spec chưa đúng?) → 3 · Agent Dev: sửa luôn (Agent QA kiểm lại từ đầu).

- **≤ 3 vòng** tự động, không chờ người.
- Pass → ticket đi tiếp sang Ready to Deploy. Quá 3 vòng → gắn nhãn `needs-human`, trả về cho người.

> **Lời thoại:** Nếu agent QA thấy lỗi thì sao? Agent QA ghi bằng chứng lỗi và tự trả ticket về. Agent Dev và agent BA phối hợp tìm nguyên nhân: lỗi do code, hay do spec chưa đúng. Agent Dev sửa luôn, agent QA kiểm lại. Vòng lặp này chạy tự động, không chờ người. Pass thì ticket đi tiếp sang Ready to Deploy. Qua ba vòng vẫn chưa pass thì ticket gắn nhãn needs-human và trả về cho người.

### 27. Ban ngày: người giữ cổng, agent chạy

| Giờ | Diễn biến | Ai |
|---|---|---|
| 09:34 | PO gọi create-task “muốn lọc briefing theo ngày”; agent hỏi lại giờ nào, mặc định ngày nào, rồi mới tạo LK-123 | PO |
| 09:49 | Agent BA soạn spec nháp LK-123, LK-128; đầu mỗi spec có mục điểm cần BA quyết | Agent BA |
| 10:02 | Cùng lúc: Agent Dev tự review LK-125 sau khi người đã merge; Agent QA kiểm đạt LK-121 | Agent Dev, QA |
| 10:14 | Dev A duyệt LK-123, Dev B duyệt LK-128 bằng task-fetch → Ready | Dev A, Dev B |
| 10:32 | Agent BA dùng BA Document soạn đoạn sửa SRS; BA duyệt một lượt mỗi ngày, chỉ trên phần thay đổi | Agent BA, BA |
| 14:02 | Dev A tự nhận LK-132 (việc nhỏ), làm cùng agent trong phiên: test trước, commit có mã việc | Dev A |
| Chiều | Reviewer merge LK-132, LK-123; Agent Dev tự review LK-123 trên dev rồi chuyển QA | Reviewer |

> **Lời thoại:** 9 giờ 30 sáng, trên board đã có nhiều task đang chạy; mỗi task ở một cột, có người hoặc agent đang giữ. PO có ý tưởng mới và gọi create-task. Agent hỏi lại cho rõ: múi giờ nào, mặc định ngày nào, một ngày hay một khoảng. PO xác nhận; agent tìm trùng rồi mới tạo LK-123. Cùng lúc Dev A cũng tạo LK-132 theo đúng các bước đó. Ngay sau đó agent BA thấy việc mới trên board và soạn spec nháp cho LK-123 và LK-128. Agent BA hỏi BA người trước, chỉ nhắc PO khi team không có BA; đầu mỗi spec nháp có mục điểm cần BA quyết. Cùng lúc agent Dev tự review LK-125 sau khi người đã merge, agent QA kiểm đạt LK-121. Dev A duyệt LK-123, Dev B duyệt LK-128 bằng task-fetch. Mỗi spec được duyệt cũng là một thay đổi của tài liệu: agent BA dùng skill BA Document soạn ngay đoạn sửa cho SRS (mục nào, trước và sau, ticket nguồn). Agent gom thay đổi theo mục; BA duyệt một lượt mỗi ngày trên phần thay đổi, không phải đọc lại cả tài liệu. Đồng ý thì agent ghi vào và tăng phiên bản. Khi tính năng release, agent đối chiếu thêm một lần với thực tế đã chạy, nên tài liệu không bao giờ cũ hơn hệ thống. Dev A thấy LK-132 là việc nhỏ, tự nhận và làm luôn cùng agent trong phiên, vẫn đúng kit. Làm trên nhánh nào là Dev A tự quyết; còn việc agent làm thì luôn ở worktree riêng. Buổi chiều reviewer đọc và merge LK-132 cùng LK-123. Người nhận hay agent nhận, board vẫn là một.

### 28. Qua đêm: người nghỉ, agent vẫn làm

| Khi nào | Diễn biến | Ai |
|---|---|---|
| 17:30 → | Agent Dev nhận việc ở Ready theo ưu tiên rồi hạn (LK-127 trước); mỗi ticket một worktree riêng | Agent Dev |
| Đêm | Agent QA kiểm LK-132, LK-123; Agent BA soạn spec LK-126 | Agent QA, BA |
| Đêm | Một test case LK-123 lỗi trên điện thoại → tự trả về, Dev và BA tìm nguyên nhân, sửa, QA kiểm lại | Các agent |
| Trước sáng | Agent đủ số merge request chờ review thì ngừng nhận việc mới: 4 MR chờ người | Agent Dev |
| 08:00 | PM đọc báo cáo ngày: đã xong, chờ người, bị chặn; điều phối qua board, không qua chat | PM |
| Sáng | LK-130 cần đổi cấu trúc dữ liệu: agent gom câu hỏi kèm đề xuất, gắn needs-human, làm việc khác | Agent, Tech Lead |
| Release | Agent xếp thứ tự (phụ thuộc, rủi ro thấp trước); người merge và bấm deploy từng task | Người |

> **Lời thoại:** 5 giờ 30 chiều, con người nghỉ, các AI agent vẫn chạy song song, liên tục: thấy việc trên board là nhận, không chờ ai gọi. Agent Dev lần lượt nhận việc ở Ready: plan, thực thi, chạy toàn bộ test rồi mở merge request. Nó nhận LK-127 trước vì PM đã xếp ưu tiên cao; agent nhận việc theo ưu tiên rồi tới hạn. Mỗi ticket agent làm nằm trong worktree riêng, không đụng chỗ người đang làm. Cùng lúc agent QA kiểm LK-132 và LK-123, hai task người đã merge từ chiều; agent BA soạn spec cho LK-126. Một test case của LK-123 trên điện thoại bị lỗi: agent QA ghi bằng chứng rồi tự trả ticket về; agent Dev và agent BA cùng tìm nguyên nhân, agent Dev sửa luôn, agent QA kiểm lại, không chờ ai, tối đa ba vòng. Agent nào đủ số merge request chờ review thì ngừng nhận việc mới. Trước khi trời sáng, bốn task đã mở merge request chờ người review. 8 giờ sáng hôm sau: nhìn board là biết task nào ở đâu, ai đang giữ. Mở một ticket là đọc được cả dòng thời gian; mỗi block chỉ nối thêm, không sửa, không xoá. PM đọc báo cáo ngày agent tổng hợp từ block: việc đã xong, việc chờ người, việc bị chặn; PM điều phối agent qua board, không qua chat. Reviewer đọc và merge các merge request qua đêm; agent Dev tự review từng task trên dev rồi chuyển QA. LK-130 cần đổi cấu trúc cơ sở dữ liệu: đây là cổng của người. Agent không tự quyết, cũng không ngồi chờ: gom câu hỏi một lượt kèm đề xuất, gắn nhãn needs-human rồi chuyển sang việc khác. Tech Lead trả lời một lần, LK-130 quay lại hàng đợi. Việc agent bỏ dở cũng không mất: agent ghi block handoff (đã thử gì, nghi nguyên nhân gì); dev nhận lại chọn sửa tiếp hay làm lại. Phiên release hằng ngày: agent xếp thứ tự, việc phụ thuộc và rủi ro thấp đi trước; mỗi task một merge request kèm bằng chứng QA và cách rollback. Người đọc, merge và bấm deploy từng task; task chỉ Done khi production chạy đúng commit đó.

### 29. AI làm phần lặp lại, người giữ phần quyết

- **BA người:** làm rõ yêu cầu cùng AI bằng BA Brainstorming · quyết các điểm agent ghi ở đầu spec, ký trước PO · duyệt một lượt phần sửa tài liệu do BA Document gom · spec sửa sau duyệt thành bản mới: chỉ duyệt lại phần khác nhau.
- **QA người:** viết test case ngay khi spec được duyệt · Agent QA chạy test trên trình duyệt thật, tóm tắt sẵn · đọc chỗ fail, chỗ nghi ngờ; chạy tay vài test case ngẫu nhiên, test khám phá · ký đạt, hoặc trả lỗi kèm bằng chứng.

Chưa có BA: agent BA soạn, PO ký thay. Chưa có QA: một dev khác, không phải người viết code, ký đạt.

> **Lời thoại:** Buổi sáng, BA và QA người vào việc; mỗi người dùng agent của vai mình. BA người làm rõ yêu cầu cùng AI bằng BA Brainstorming, quyết các điểm agent ghi ở đầu spec rồi ký trước PO, và duyệt một lượt phần sửa tài liệu do BA Document gom. Spec sửa sau khi duyệt thành bản mới, người chỉ duyệt lại phần khác nhau; dev đang làm mà spec đổi thì ticket về Ready. QA người viết test case ngay khi spec được duyệt. Agent QA chạy test trên trình duyệt thật và tóm tắt sẵn; ticket đạt hết chỉ một dòng. QA đọc chỗ fail và chỗ nghi ngờ, chạy lại tay vài test case chọn ngẫu nhiên, test khám phá rồi ký đạt, hoặc trả lỗi kèm bằng chứng. AI làm phần lặp lại; người giữ phần quyết và chịu trách nhiệm như trước. Team chưa có BA thì agent BA soạn, PO ký thay. Team chưa có QA thì một dev khác, không phải người viết code, ký đạt. Nhìn tổng thể: luồng BA (spec, SRS), luồng QA (test case) và luồng Dev (ticket ở Ready đang được code) chạy cùng lúc. Ban ngày người duyệt ở các cổng; ban đêm agent làm tiếp những việc đã đủ điều kiện. Sáng ra mọi người có báo cáo và một hàng việc chờ duyệt.

## Tổng kết và áp dụng cho dự án cũ

### 30. Mỗi vai trò nhận được gì

- **PO:** ý tưởng thành ticket rõ ràng. **BA:** tài liệu luôn khớp thực tế. **QA:** test case, bằng chứng có sẵn.
- **Dev:** bớt việc lặp lại, tập trung phần khó. **PM:** nhìn một board là biết cả dự án.

> **Lời thoại:** Tóm lại, mỗi vai trò nhận được gì. PO: ý tưởng thành ticket rõ ràng. BA: tài liệu luôn khớp thực tế. QA: test case và bằng chứng có sẵn. Dev: bớt việc lặp lại, tập trung vào phần khó. PM: nhìn một board là biết cả dự án.

### 31. Một mô hình vận hành chung cho người và AI

- **Nhìn thấy:** board của mọi team: việc ở đâu, ai giữ. **Kiểm soát:** cổng của người, luật do máy kiểm, chi phí có trần.
- **Đo được:** so với hiện trạng, theo team, không xếp hạng cá nhân. **Khả thi:** đã chạy thật ở quy mô một người, nhân rộng bằng pack riêng.
- **Cổng của người:** chốt ý tưởng · duyệt spec · quyết định khó đảo ngược (contract, migration, bảo mật) · merge · deploy.
- **Agent làm, kèm bằng chứng:** làm rõ · code · test · tự review · QA · gắn SHA, ảnh, log, cả ngày lẫn đêm.
- **Kit AI Workflow · nền chung cho mọi team** (mỗi team thêm pack riêng, phần lõi giữ nguyên): Luật chung · Skill · Hook · Mẫu commit · Bản đồ module · Tự cập nhật.

> **Lời thoại:** Ghép hai phần lại thành một mô hình vận hành. Nền dưới cùng là kit AI Workflow: một bộ luật, skill và hook cho mọi team; mỗi team thêm pack riêng, phần lõi giữ nguyên. Trên nền đó, mỗi team có Space riêng trên Linkup; trong team có PM, PO, Dev, BA, QA và các AI agent cùng nhận việc trên một board. Con người giữ ý định và các cổng: chốt ý tưởng, duyệt spec, quyết định khó đảo ngược, merge và deploy. AI agent làm phần còn lại, cả ngày lẫn đêm, luôn kèm bằng chứng. Từ góc nhìn quản lý: nhìn thấy board của mọi team; kiểm soát bằng cổng của người, luật do máy kiểm và chi phí có trần theo từng dự án; đo so với hiện trạng, theo team, không xếp hạng cá nhân. Mô hình đã được nghiên cứu và chạy thật ở quy mô một người, áp dụng cho toàn team, rồi nhân rộng sang các team khác chỉ bằng một pack riêng.

### 32. Dự án cũ: khôi phục tài liệu từ code trước

Chưa có tài liệu, thiếu test → chưa giao agent tự chạy được. Bước đầu: khôi phục bộ tài liệu.

1. **Dev code cùng agent:** Agent: “Luồng xuất CSV đi qua module nào? Vì sao bỏ dòng trống?” – Dev: “briefing → export. Khách yêu cầu bỏ dòng trống. Xác nhận.” → `+ export/docs/luong-xuat-csv.md`.
2. **PM, BA, PO dùng BA Document:** quét `briefing/docs`, `export/docs`, `notify/docs` → tổng hợp thành SRS chức năng cũ.
3. **SRS bản khôi phục:** 4.2 Xuất CSV; nguồn: dev đã xác nhận, nên độ tin cậy cao hơn; người quản lý tài liệu duyệt.

Tài liệu bổ sung dần; chức năng nào đủ SRS và test thì bật agent tự động cho nó.

> **Lời thoại:** Dự án cũ: chưa có tài liệu, chưa đủ test, nên chưa thể giao ngay cho AI agent tự chạy. Việc đầu tiên là khôi phục lại bộ tài liệu. Kit có thêm một luật nhỏ: khi AI code cùng dev, nó khám phá luồng hoạt động xuyên các module và đặt câu hỏi ở những chỗ chưa rõ. Ví dụ: chức năng này chạy theo luồng nào, vì sao lại xử lý như vậy? Dev xác nhận, agent ghi ngay vào thư mục tài liệu của module đó. Sau đó PM, BA hoặc PO dùng agent BA Document quét các thư mục tài liệu ấy, tổng hợp thành SRS cho những chức năng cũ. Vì dev đã xác nhận nên độ tin cậy cao hơn, nhưng người quản lý tài liệu vẫn duyệt lại cho đúng và chuẩn. Tài liệu được bổ sung dần dần. Chức năng nào đã có SRS và test đầy đủ thì bật agent tự động cho chức năng đó.

### 33. AI tăng tốc phần làm. Quy trình giữ phần đúng. Con người giữ phần quyết.

Nội dung từ video “AI Workflow – Quy trình phát triển dự án cùng AI” · tác giả kiến trúc: Hưng Khánh.

> **Lời thoại:** AI tăng tốc phần làm, quy trình giữ phần đúng, con người giữ phần quyết.
