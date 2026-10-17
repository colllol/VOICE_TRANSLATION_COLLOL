# VT-023 setup preview — checkpoint 2026-10-17

- Attempt setup-preview-20261017; branch codex/VT-023-preview.
- Không khởi chạy worker khác; kiểm process/git trước khi làm. Không sửa docs/ untracked.
- Setup UI: chọn hai ngôn ngữ, swap, chặn ngôn ngữ giống nhau, readiness check báo chưa tích hợp, Close.
- Không tạo trạng thái giả đang dịch, không thêm quyền mic/network, không audio cá nhân.
- Build lần đầu lỗi tên API anchor; sửa dùng menuAnchor() tương thích dependency hiện tại (còn deprecation warning).
- assembleDebug + lintDebug PASS: 48 tasks (16 executed, 32 up-to-date).
- adb install -r: Success; am start -W: Status ok, COLD 2495ms; pidof 26707. Đây là startup không phải latency dịch.
- python backend/smoke.py sai cách gọi (ModuleNotFoundError); chạy python -m backend.smoke PASS. tools/check_repo.py PASS.
- Chưa xác minh thao tác UI/ảnh chụp; chưa reviewer độc lập. Không đánh Done, không merge/push DEV.
- Harness delta: chưa thêm automated UI tests; đây là khoảng trống cần bổ sung.
- Next: UI interaction tests/review; VT-005 controlled VoIP peer thật + VT-003 inference benchmark vẫn là gate bắt buộc.
