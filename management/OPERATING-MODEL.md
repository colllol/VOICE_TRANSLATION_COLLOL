# Operating model — Codex + Claude

Cập nhật: 2026-10-13

## Phạm vi đợt thiết lập
Yêu cầu hiện tại cho phép dựng bộ máy phân công, kiểm tra model, ghi nhật ký và commit/push.
Chưa tự triển khai toàn bộ app theo những sơ đồ còn điểm sai. Ticket dưới đây là kế hoạch triển khai;
đánh Planned cho tới khi có dispatch thực, không nhầm phân công trên giấy với agent đang chạy.

## Cấp quản lý và quyền ghi
- Quản lý chung: Codex trong phiên điều phối hiện tại; chịu trách nhiệm sản phẩm, contract, DAG,
  khóa phạm vi, giải quyết tranh chấp, review chéo và tích hợp DEV. Model CLI đã kiểm tra:
  `gpt-6-astra`, xhigh; provider cấu hình `vietapi`, không coi là xác minh backend model của nhà cung cấp.
- Quản lý Codex: phiên Codex riêng, ưu tiên cùng model đã kiểm tra cho Android/audio,
  Gradle/build, fixture và integration. Tự chia task nhỏ trong phạm vi đã giao; không tự merge DEV.
- Quản lý Claude: phiên Claude riêng, dùng alias `opus` cho kiến trúc AI/protocol và review;
  alias này đã trả lời consultation, chưa xác minh được canonical model từ metadata.
- Worker Codex: Android/audio/runtime và harness. Worker Claude: backend/pipeline/ngữ cảnh/training.
- Reviewer khác owner, không tự duyệt task của mình. Manager không được báo việc hoàn tất thay
  cho bằng chứng build/test và behavior thực tế.

## Nguồn công việc và Obsidian
Ticket trong `management/backlog/VT-xxx.md` là nguồn trạng thái chính, STATUS là chỉ mục dẫn xuất.
Vault là bộ nhớ bền vững về lý do, checkpoint và thực nghiệm; `Task-list.md` phản chiếu trạng thái ticket.
Một task gồm owner/manager/reviewer, dependencies, scope, branch, acceptance và evidence.
Không tạo ticket trùng ID: đối chiếu cả ticket files và danh sách VT cũ trong vault trước khi cấp số mới.
Một người viết mỗi file: worker chỉ ghi log của mình; manager chỉ ghi log đội; coordinator tổng hợp.
Các log giữ lịch sử, sửa `Cập nhật:` và thêm mục có ngày/giờ Asia/Saigon.
Trước compaction, kết thúc turn, trước/sau test, commit hoặc lỗi: ghi checkpoint.

## Vòng làm việc
1. GM chọn wave có dependencies hoàn tất, ghi owner và scope; manager chuẩn bị prompt từ template.
2. Worker đọc repo/vault, báo nhận task và model hiệu lực; ghi attempt/session/host/worktree vào log.
3. Thực hiện thay đổi trong scope; sau mỗi phần chức năng chạy kiểm tra phù hợp và commit nhỏ.
4. Worker gửi commit hash, file list, lệnh kiểm tra, pass/fail/count, quan sát thực tế, điểm chưa kiểm chứng.
5. Manager review; đội còn lại kiểm tra độc lập phần tích hợp. GM mới chuyển Reviewed → Done và push DEV.
6. GM cập nhật STATUS và note tổng hợp, không xóa lịch sử cũ.

## Git
Đầu wave fetch origin DEV, kiểm tra diff và nhánh; không dùng reset/switch -C để ghi đè.
Tạo nhánh từ origin/DEV và checkout cô lập nếu nhiều worker viết song song.
Worker stage file có chủ đích, không `git add .` khi có file ngoài scope; không commit secret/model weights/audio cá nhân.
Commit `<area>: <feature> [VT-xxx]`. WIP được giữ bằng commit riêng ghi rõ chưa qua checks,
không merge vào DEV. GM tích hợp tuần tự, chạy checks liên quan rồi `git push origin DEV`.
Nếu remote thay đổi: fetch và review/reconcile; không force. Ghi cả local commit lẫn remote hash sau push.

## Giám sát và tiếp tục
Trong một run đang sống, manager kiểm tra worker mỗi 60 giây; checkpoint mục tiêu mỗi 5 phút
và tại mốc tự nhiên. Quá 15 phút không tiến triển là tín hiệu kiểm tra, KHÔNG phải chứng cứ đã chết.
- Live + tool/test đang chạy: tiếp tục chờ, xem output mới, không gửi prompt chen ngang.
- Đang chờ trả lời: giải quyết câu hỏi thuộc phạm vi được giao; không bypass auth/permissions.
- Final turn chưa báo Done: đọc report, git/checkpoint, giao tiếp phần còn thiếu cho cùng owner.
- Exit/crash xác minh được: giữ worktree, ghi attempt thất bại; manager tạo attempt tiếp theo
  cùng task từ checkpoint. Tối đa 2 retry sau attempt đầu; 3 lỗi liên tiếp → escalate GM.
- Không xác minh được liveness / mất liên lạc: giữ trạng thái Unknown, không spawn bản sao,
  không kill/reset hoặc merge phần việc đó.
Sau restart toàn bộ máy/app: đọc checkpoint và enumerate worker/process trước khi resume.
Không có yêu cầu retry khi người dùng chủ động dừng/huỷ. Không tái chạy push/deploy khi kết quả mơ hồ;
kiểm tra remote trước. Không rollback thay đổi người dùng.

## Runtime thực tế, không giả định
Orca 1.4.224 đã chạy và nhận repo. Phiên chat này không có sender terminal:
`orca orchestration run-create ...` trả `no_active_sender_terminal`.
Do đó CHƯA có Run/Dispatch và CHƯA có giám sát nền hoạt động. Hai consultation CLI là phiên
độc lập có kết thúc, không phải worker Orca và không được gắn ID giả.
Để chạy wave dưới Orca: mở phiên coordinator thực trong terminal Orca của repo, đọc
`orca skills get orchestration`, xác minh `orca status --json`, rồi tạo run từ terminal của chính mình.
Không gán `--from` bằng handle của một pane khác. Dùng worker-start cho hai manager; task spec
có scope/evidence đầy đủ; model chọn theo availability. Manager chỉ spawn worker nếu runtime
cho phép độ sâu; nếu không, gửi GM tạo worker thay vì tạo run để lách giới hạn.
Sau worker_done: GM/manager quyết định reuse hoặc release trước khi ack. Dùng chỉ dẫn recovery
của đúng CLI; timeout không tự động cho phép retry. Chưa cấu hình scheduler/daemon 24/7.
