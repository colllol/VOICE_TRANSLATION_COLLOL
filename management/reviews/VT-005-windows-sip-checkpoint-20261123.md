# VT-005 — Kiểm tra SIP trên Windows

Nhánh `dev-computer`, base `3fe2ff4`. Thay đổi nghiên cứu đang ở worktree, chưa commit. Vault `C:/Users/Admin/Documents/Codex Knowledge` chưa truy cập được từ phiên này. Checkpoint lưu tại repo.

- Baresip 4.13.0 và libre build thành công bằng MSYS2 UCRT64. WASAPI đã compile/link. Cấu hình libre cần `USE_REM=ON` để cung cấp symbol audio.
- Hai tiến trình trên cùng máy thiết lập SIP/RTP loopback dùng PCMU 8 kHz. Khi chỉ A nạp filter, mỗi cửa sổ 8.000 mẫu tại đầu nhận có đúng mức fixture dự kiến: A `-3000`, B `3004` sau lượng tử hóa G.711. Baseline có biên độ `[-8316, 8316]` ở cả hai đầu. Chạy với yêu cầu replacement nhưng thiếu module làm assertion thất bại.
- Sau review, probe kiểm tra codec từ log và xác nhận đúng tần số của đầu bên kia ở cả hai hướng. Baseline và replacement đều qua với `python -O`; đối chứng `--replacement --omit-filter` trên cùng binary thoát mã 1 với 8.000 mẫu sai tại A. Bộ test backend và route đạt `81 passed, 51 warnings`. Fixture chỉ kiểm tra cửa sổ WAV một giây; chưa chứng minh startup, teardown hoặc phát hiện mất/lặp mẫu trong suốt cuộc gọi.
- Trong Baresip ở revision đã ghim, lỗi callback encode được ghi log và frame vẫn đi tới `encode_rtp_send`. Cần kiểm chứng việc chặn PCM gốc tại đường gửi khi provider lỗi hoặc chưa có bản dịch.
- Còn thiếu tích hợp Windows–backend, mic/loa WASAPI trên laptop, cuộc gọi với SIP client B độc lập và người nghe hai đầu, cùng kết quả stop, lỗi provider, reconnect, độ trễ và độ rõ lời nói. VT-005 vẫn mở.
- Ranh giới tích hợp đề xuất: callback chỉ xử lý PCM và không chờ I/O; worker riêng chuyển đổi 8/16 kHz và dùng WebSocket loopback `chunks-v1` với hai hàng đợi giới hạn độc lập. Không dùng `audio.input` cho Azure hoặc coi cả đoạn thu là frame 20 ms. Khi bật dịch, chưa có kết quả hoặc provider lỗi phải ra im lặng; kết quả phiên cũ phải bị loại bỏ. Product bridge và hủy provider thực sự thuộc scope tích hợp cần duyệt riêng; checkpoint này không thay đổi backend/app.

Build và lệnh tái hiện nằm trong `research/audio_route/windows-voip-spike.md`.
