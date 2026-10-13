# Model routing và bằng chứng

Cập nhật: 2026-10-13

## Đã kiểm tra
- Codex CLI 0.160.0. Lượt consultation read-only báo model `gpt-6-astra`, effort `xhigh`, provider `vietapi`.
  Đây là tên do runtime khai báo, không chứng minh model phía sau gateway. Không ghi giá trị credential.
- Claude Code 2.1.239, auth status loggedIn=true. Consultation `--model opus` trả nội dung thành công.
  `--output-format json` trả text thuần trong môi trường hiện tại; chưa có canonical model metadata.
- Orca runtime ready, version 1.4.224; run-create bị chặn do không có sender terminal của phiên này.

## Lựa chọn theo loại việc
- GM: Codex/Astra cấu hình hiện tại, xử lý thay đổi xuyên module, tích hợp và kiểm chứng.
- Codex manager: Astra cho Android audio/lifecycle/VoIP, debug khó và review integration.
- Codex worker: model mặc định đã được kiểm tra; thử Sol cho task coding vừa và Luna cho task nhỏ
  chỉ sau smoke test về build/độ đúng. Không tự đổi model đang chạy dựa trên tên marketing.
- Claude manager: Opus cho phân rã backend, phản biện pipeline và kiểm tra voice preservation.
- Claude worker: Sonnet ứng viên cho FastAPI/adapters/tests; Haiku ứng viên cho triage/log/docs.
  Hai alias này chưa chạy thử trong phiên này; dùng Opus đã phản hồi nếu cần bắt đầu ngay.
- Task nhỏ vẫn cần reviewer mạnh khi chạm quyền Android, audio routing, session protocol, secrets.

## Căn cứ tài liệu chính thức đã tải ngày 2026-10-13
- https://developers.openai.com/codex/models/ : đề xuất GPT-6.1 Sol cho coding/agentic phức tạp
  khi tài khoản hỗ trợ, Luna cho việc tập trung/lặp lại, Astra cho reasoning và công việc khó.
- https://platform.claude.com/docs/en/models/overview : Opus 5.5 cho coding dài hơi,
  Sonnet 5.5 cân bằng tốc độ/chất lượng, Haiku 5.5 cho tác vụ nhanh; Fable 5.1 cho reasoning khó.
Các model trong tài liệu không đồng nghĩa tài khoản/gateway cục bộ cho phép dùng.
Không có benchmark đối đầu của repo; phân công trên là giả thuyết công việc, đánh giá lại sau wave 0.

## Khi dispatch
Ghi requested alias, effective model từ launcher/provider nếu có, effort, CLI version,
provider label, session/dispatch ID, ngày giờ, test probe. Thiếu effective model → Unknown,
không dùng lời tự nhận trong câu trả lời để chứng minh model. Không tải hoặc log file auth.
