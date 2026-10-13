# VT-003 — rà giấy phép và khả năng streaming (nguồn chính thức)

Cập nhật: 2026-10-13. **Chưa có phép đo inference, WER, chất lượng dịch hoặc độ trễ.**
Claude tạo khung audit khi phiên của Claude không có mạng; coordinator kiểm tra lại nguồn bên dưới.

## Faster-Whisper (ASR)

- File LICENSE chính thức của `SYSTRAN/faster-whisper`: **MIT License**; hỗ trợ sử dụng/sửa/phân phối theo điều khoản ghi công của MIT.
  Nguồn đọc trực tiếp: https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/LICENSE
- Đóng gói Whisper trên CTranslate2; không giả định streaming ASR end-to-end chỉ bằng API batch. Cần chunk/VAD và đo hội thoại thực.
  Repo: https://github.com/SYSTRAN/faster-whisper
- Model size/revision/compute type/hỗ trợ cụ thể sáu ngôn ngữ và license model weights: **chưa chốt**, kiểm theo artifact được chọn.

## NLLB-200 Distilled 600M (NMT)

- Model card chính thức ghi `license: cc-by-nc-4.0`; **không coi là mặc định cho mục đích thương mại**.
- Card mô tả model chủ yếu cho **research**, dịch theo **single sentence** trong 200 ngôn ngữ, không phát hành cho production. Dữ liệu huấn luyện general-domain, chuỗi dài hơn 512 tokens có thể suy giảm chất lượng. Không được tuyên bố tự có bộ nhớ hội thoại: cần context builder/đánh giá riêng.
- Nguồn đọc trực tiếp: https://huggingface.co/facebook/nllb-200-distilled-600M/raw/main/README.md
- Hỗ trợ vi/en/zh-Hans/ru/de/es theo lý thuyết phải kiểm mã ngôn ngữ cụ thể và chất lượng từng hướng; 30 hướng chưa đo.

## Google Cloud Text-to-Speech

- Tài liệu Google Cloud có **bidirectional streaming synthesis**; trang quickstart ghi hiện **chỉ tương thích với Chirp 3: HD voices**. Không suy từ đó rằng WaveNet/Neural2/Studio hỗ trợ streaming.
  Nguồn: https://cloud.google.com/text-to-speech/docs/create-audio-text-streaming
- Bảng giá truy cập 2026-10-13 ghi Chirp 3: HD: 0–1 triệu ký tự free tier; sau đó USD 30/1 triệu ký tự. Các voice khác có SKU và giá riêng; kiểm tại thời điểm sử dụng. Chưa gọi API trả phí.
  Nguồn: https://cloud.google.com/text-to-speech/pricing
- `voice_name` và biến thể vùng miền cho đủ 6 ngôn ngữ, quota, credential/billing và khả năng giữ identity: **chưa xác minh**. Google TTS thông thường không tự duy trì giọng gốc của hai người; thử voice conversion/provider có consent ở VT-025.

## Gate còn thiếu

1. Chốt sáu mã nguồn/đích, voice ID và revision từng model, kiểm license cả weights và SDK.
2. Chạy trên Windows local CPU/GPU thực và Android thật; lưu hardware, lệnh, dataset hợp lệ, p50/p95 trực tiếp từ sự kiện theo từng utterance/direction.
3. Đo A→B và B→A, cold/warm, end-to-first-audio của *voice nghe được tại người nhận*, không thay bằng subtitle hay số tổng hợp từ các tầng.
4. Nếu thiếu credentials/billing/dataset thì ghi `Blocked`, không điền số giả; chỉ dùng số marketing như thông tin tham khảo có nhãn rõ.