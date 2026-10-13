# Quy tắc chung cho mọi agent

Cập nhật: 2026-10-13

- Đọc file này, `management/OPERATING-MODEL.md`, `management/backlog/STATUS.md` và ticket được giao trước khi sửa.
- Vault chính: `C:/Users/Admin/Documents/Codex Knowledge`. Đọc `Projects/Index.md`, rồi `Projects/VOICE_TRANSLATION_COLLOL/Overview.md`, `Progress.md`, `Decisions.md` và log của mình. Kiểm chứng lại thông tin cũ với repo.
- Ràng buộc: chỉ A cài/điều khiển công cụ; B tham gia cuộc gọi thông thường, không phải cài công cụ dịch. Audio hai chiều; đầu ra voice. Text ASR/NMT chỉ dùng nội bộ. Không thêm bước B xác nhận trong UX dịch.
- Demo đầu tiên dùng VoIP có điểm tích hợp do dự án kiểm soát tại A. Không hứa có thể chặn/chèn audio của mọi app Android. AudioTrack phát loa không đồng nghĩa outbound-track injection.
- Bảo toàn giọng và độ trễ audio <1s là mục tiêu phải đo, chưa đạt mặc định. Không tự loại bỏ yêu cầu khi gặp khó; trình phương án và bằng chứng cho quản lý chung.
- Mỗi task chỉ có một owner và một attempt đang có quyền ghi. Chỉ sửa file scope ticket. Không sửa contract dùng chung khi chưa được quản lý chung điều phối.
- Base `origin/DEV`; nhánh `codex/VT-xxx` hoặc `claude/VT-xxx`. Mỗi tính năng đủ kiểm tra commit ngay, ghi mã task. Chỉ quản lý chung merge/push vào `DEV`. Không push main, force-push hoặc reset bỏ dữ liệu.
- Ghi nhật ký riêng trong vault tại `Projects/VOICE_TRANSLATION_COLLOL/Agent-logs/Workers/<agent-id>.md`. Ghi task/attempt, branch, commit, checkpoint, kết quả kiểm tra, lỗi, bước tiếp theo. Không ghi secrets hoặc audio cá nhân.
- Manager ghi log riêng. Chỉ quản lý chung sửa các trang tổng hợp Overview/Progress/Decisions/Known-issues/Task-list/Feature-register để tránh xung đột ghi.
- Chưa đọc/ghi được vault: báo ngay, tạo checkpoint cục bộ ở `management/reviews/`, không tự nhận đã đồng bộ. Không đánh Done đến khi log đã được đối chiếu.
- Trước khi tiếp tục attempt: kiểm tra process, trạng thái git, log gần nhất và owner. Im lặng không chứng minh process đã chết; không khởi chạy worker trùng.
- Không ghi Done chỉ vì agent nói xong. Cần commit, checks có kết quả và người review khác xác nhận. Nếu thiếu thiết bị/GPU/key thì ghi rõ blocked, không giả lập bằng chứng.
- File Draw.io và tài liệu ý tưởng không chứng minh API Android hoặc model đã hoạt động. Báo mâu thuẫn thay vì triển khai theo sơ đồ chưa kiểm chứng.
