# VT-003 — chuẩn bị benchmark

Cập nhật: 2026-10-13

Chưa có phép đo inference. Không tìm thấy nvidia-smi trên PATH; điều này không chứng minh
máy không có GPU. Chưa tải model, chưa gọi API trả phí, chưa có corpus test được chốt.

Mỗi phép đo cần: commit, command, OS/CPU/GPU/RAM, model id/revision/hash, runtime/version,
quantization/threads, ngôn ngữ, corpus version/license, độ dài audio, sample rate, warm/cold
(load có nằm trong thời gian không), số mẫu, timestamps, p50/p95 và lỗi.
Đo riêng ASR/NMT/TTS và end-to-first-audio, không cộng percentile các tầng để giả định p95 tổng.

So sánh 6 ngôn ngữ vi/en/zh-Hans/ru/de/es (30 hướng); benchmark sâu các cặp đại diện.
Faster-Whisper cần chunking/stabilization để dùng liên tục; không là streaming ASR nguyên bản.
NLLB: kiểm license/model card, giới hạn context; Google TTS: kiểm voice/language/quota và khả năng
streaming của voice cụ thể. Giữ giọng cần pipeline riêng, không tiêm embedding tùy ý vào Google TTS.

Reviewer Claude đã chỉ ra metadata trên trong lượt review foundation. Cần dataset và cấu hình
máy chạy thực tế trước khi đưa ra kết luận tốc độ/chất lượng hoặc model thắng.
