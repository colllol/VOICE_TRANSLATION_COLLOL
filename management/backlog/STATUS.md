# STATUS — công việc chung

Cập nhật: 2026-10-13

VT-001 Done; các ticket còn lại chưa nghiệm thu.
ID VT-001..004,010..013,020..023,030..033 được kế thừa từ vault; bổ sung 005,014,024..026 sau đối chiếu ID.

## Quyền và ràng buộc
Chủ đồ án đã yêu cầu chia việc và commit DEV. Ticket là kế hoạch được phép lưu; thay đổi sản phẩm/contract chưa chốt phải đưa GM duyệt trước code.
Wave đầu đã chạy VT-001/VT-003/VT-005; VT-005 vẫn blocked device proof; VT-002 sau bằng chứng 005; VT-004 gate trước phần còn lại.

## Backlog
- [VT-001 — Nền tảng monorepo và CI](VT-001.md): Done · Codex · dependencies: none
- [VT-002 ? H?p ??ng session v? audio transport](VT-002.md): In progress ? contract reviewed, runtime gate open ? Claude ? dependencies: VT-005
- [VT-003 — Benchmark và license ASR NMT TTS](VT-003.md): In progress — benchmark blocked · Claude · dependencies: none
- [VT-004 — Chốt gate kiến trúc demo](VT-004.md): Planned · Codex · dependencies: VT-002, VT-003, VT-005
- [VT-005 — Feasibility VoIP hai chiều chỉ A điều khiển](VT-005.md): In progress — device proof blocked · Codex · dependencies: none
- [VT-010 ? FastAPI WebSocket session service](VT-010.md): In progress ? core service only, transport gate open ? Claude ? dependencies: VT-001, VT-002, VT-004
- [VT-011 — Android capture và lifecycle](VT-011.md): Planned · Codex · dependencies: VT-001, VT-004
- [VT-012 ? ASR NMT TTS adapters](VT-012.md): In progress ? fake boundary reviewed, real provider gate open ? Claude ? dependencies: VT-003, VT-010
- [VT-013 — Điều phối dịch hai hướng](VT-013.md): Planned · Claude · dependencies: VT-010, VT-011, VT-012
- [VT-014 — Tích hợp outbound và inbound VoIP tại A](VT-014.md): Planned · Codex · dependencies: VT-005, VT-011, VT-013
- [VT-020 — AEC NS AGC và chống feedback](VT-020.md): Planned · Codex · dependencies: VT-011, VT-014
- [VT-021 — VAD và ổn định cụm nói](VT-021.md): Planned · Claude · dependencies: VT-012, VT-013
- [VT-022 — Adaptive Controller và phép đo](VT-022.md): Planned · Codex · dependencies: VT-020, VT-021
- [VT-023 — UI app popup chỉ cho A](VT-023.md): In progress — setup preview only · Codex · dependencies: VT-011, VT-013
- [VT-024 — Ngữ cảnh và glossary](VT-024.md): Planned · Claude · dependencies: VT-012, VT-021
- [VT-025 — Voice identity xuyên ngôn ngữ](VT-025.md): Planned · Claude · dependencies: VT-003, VT-012
- [VT-026 — Training giọng vùng miền](VT-026.md): Planned · Claude · dependencies: VT-003, VT-024, VT-025
- [VT-030 — Ma trận 6 ngôn ngữ và full duplex](VT-030.md): Planned · Codex · dependencies: VT-014, VT-020, VT-021, VT-022, VT-023, VT-024, VT-025
- [VT-031 — Retention consent và bảo vệ dữ liệu](VT-031.md): Planned · Claude · dependencies: VT-010, VT-023, VT-025, VT-026
- [VT-032 — APK và kịch bản bảo vệ đồ án](VT-032.md): Planned · Codex · dependencies: VT-030, VT-031
- [VT-033 — Review chéo và tích hợp cuối](VT-033.md): Planned · Codex · dependencies: VT-032

## Thiết lập đã thực hiện
- Operating model, AGENTS/CLAUDE entry points, model routing và prompt template đã tạo.
- Claude consultation hoàn tất; Codex consultation hoàn tất (exit 0).
- Chưa có Orca Run: no_active_sender_terminal. Không có worker implementation đang được quản lý bởi bộ board này.
- [VT-034 — Mở rộng CI cho backend transport và contract](VT-034.md): Planned · Claude · dependencies: VT-002, VT-010, VT-012
