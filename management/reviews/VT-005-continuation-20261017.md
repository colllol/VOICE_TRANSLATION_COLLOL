# Checkpoint VT-005 — 2026-10-17

- Tiếp tục theo kế hoạch từ branch `codex/VT-023-preview`; giữ `docs/` untracked, không đụng file người dùng.
- Trạng thái đầu lượt: branch preview commit `f977393`, ahead origin/DEV một commit; ADB có hai transport cùng serial Redmi K70, không đổi nhánh/merge.
- Kiểm tra theo transport 8 xác nhận model `23113RKC6C`, Android 16. Thiết bị khóa PIN; `dumpsys window` thấy NotificationShade/keyguard, không nhập PIN. App package cài và task MainActivity tồn tại nhưng UI chưa có foreground focus.
- `python -m unittest research.audio_route.test_route -v`: PASS 13/13.
- `python -m unittest research.models.test_benchmark -v`: BLOCKED môi trường. 10/12 lỗi ở tempfile `events.jsonl` với PermissionError; các test trên temp OS và `.test-tmp` đều bị chặn. Đã thử TEMP/TMP trong workspace; dọn `.test-tmp` bị PermissionError, còn thư mục test rỗng/không thể đọc do sandbox ACL. Không sửa test source.
- `python -m backend.smoke`: PASS, chỉ import/health smoke; không chạy server/model.
- `python tools/check_repo.py`: PASS; `git diff --check`: PASS.
- Toolchain hiện có SDK platform 36/build-tools 35/36 và JDK21; không thấy Android NDK/CMake SDK hoặc PJSIP source/binary trong repo.
- Chỉ có một thiết bị Android, không có peer B. Không có media/VoIP proof A-E. VT-005 vẫn blocked; VT-004 chưa đủ dependency evidence. Không tạo implementation giả.
- UI test thủ công không hoàn tất do máy khóa PIN. Người dùng yêu cầu không kiểm tra xoay màn hình; không làm test ấy.
- Next: cần owner mở khóa Redmi K70 để tiếp tục UI test và cung cấp/duyệt peer VoIP B + chọn SDK/endpoint PJSIP hoặc giải pháp có media hooks. Sau đó mới spike native Android và chạy gate A-E. Benchmark suite cần runner/temp workspace có ACL ghi được; chưa có model/API/corpus hợp lệ.
