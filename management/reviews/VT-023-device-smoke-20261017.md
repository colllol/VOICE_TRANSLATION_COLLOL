# Checkpoint VT-023 / VT-005 — 2026-10-17 (continuation)

- Tiếp tục trên branch `codex/VT-023-preview`; không sửa `docs/` hoặc file tổng hợp ngoài scope.
- ADB hiện có Redmi K70 model `23113RKC6C`, Android 16/API 36; hai transport cùng serial, dùng transport 15. Thiết bị đã mở khóa (`mDreamingLockscreen=false`, MainActivity foreground).
- UI smoke bằng `uiautomator` trên APK đã cài: MainActivity start `Status: ok`, dropdown mở được và liệt kê 6 ngôn ngữ; chọn ngôn ngữ; đổi A↔B; nút kiểm tra hiện fail-closed “Chưa thể bắt đầu dịch...” và không khởi chạy phiên; Đóng đưa focus về `com.android.settings`.
- Cập nhật copy UI bỏ câu “giữ khi xoay màn hình” theo yêu cầu người dùng; thay bằng cấu hình chỉ có hiệu lực trong phiên hiện tại.
- `assembleDebug + lintDebug`: PASS, 48 tasks (12 executed, 36 up-to-date); chỉ warning deprecated `Modifier.menuAnchor()`.
- `adb install -r`: Success; `am start -W`: Status ok, COLD, TotalTime 709 ms. Đây là startup, không phải latency dịch.
- `python -m backend.smoke`: PASS; `python tools/check_repo.py`: PASS; `git diff --check`: PASS trước commit.
- Commit `35b3913 android: clarify session-only language config [VT-023]`; không push/merge DEV.
- Chưa có VoIP SDK/media hook, peer B hoặc gate A–E; VT-005 vẫn blocked cho bằng chứng audio hai chiều. UI pass không chứng minh dịch voice.
- Chưa kiểm tra xoay màn hình theo yêu cầu người dùng.
