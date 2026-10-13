# Instrumentation schema v1

Chỉ dùng cho phép đo **thực**. Một dòng JSONL/event gồm `session_id`, `utterance_id`,
`direction` (`a2b`/`b2a`), `event` (`capture_end`, `asr_end`, `nmt_end`, `first_audio`),
`timestamp_ms` monotonic cùng clock domain. Dòng `capture_end` bắt buộc có
`warm_state` (`cold`/`warm`) do runner xác định theo load model, không suy từ thứ tự dòng.
`first_audio` là audio đã được render tại người nhận (B cho A→B, A cho B→A),
không phải lúc server bắt đầu tạo TTS. Muốn đo network/to-device cần timestamp
trong clock domain đồng bộ hoặc conversion đã đo; không trộn clock của các máy.

Ví dụ kỹ thuật (synthetic, KHÔNG phải benchmark):
`{"session_id":"s","utterance_id":"u1","direction":"a2b","event":"capture_end","timestamp_ms":100,"warm_state":"warm"}`

Chạy: `python -m research.models.benchmark_harness path/to/events.jsonl`.
Report chia theo direction và cold/warm; p50/p95 tính tuyến tính trên [0,n-1],
có n; mẫu thiếu/duplicate/nonmonotonic làm exit 1. Mọi kết quả n nhỏ chỉ báo
thử harness; không suy diễn độ trễ sản phẩm.