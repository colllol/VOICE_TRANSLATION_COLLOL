# PJSIP Android media-port spike — VT-005

Cập nhật: 2026-10-17

## Mục tiêu

Kiểm tra độc lập xem PJSIP/PJSUA2 có thể biên dịch native cho Android arm64 và có
điểm móc media để thay frame outbound/inbound hay không. Đây **không** phải tích hợp
vào APK và không chứng minh cuộc gọi thật.

## Bằng chứng đã quan sát

- Source: PJSIP tag `2.17`, tag commit `6852b24c0d07219a06130ae982320942241eee49`;
  shallow checkout source commit `5a457451fa2712ba18e12b01738e8ff3af2b26fd`.
- Toolchain ngoài repo: Android NDK r26d (`26.3.11579264`), CMake 4.3.2, Ninja
  1.12.1; output đặt trên ổ D vì ổ C gần đầy.
- CMake Android toolchain: ABI `arm64-v8a`, API `android-29`. Bản copy spike tắt
  video/audio-device và các codec tùy chọn không cần cho kiểm tra media core.
- CMake configure pass; Ninja build pass cho target `pjsua2`, tạo
  `libpjsua2.a` 8,589,788 bytes cùng các static library pjlib/pjmedia/pjsip.
- `llvm-nm -C libpjsua2.a` xác nhận symbol:
  `pj::AudioMediaPort::createPort`,
  `pj::AudioMediaPort::onFrameRequested`,
  `pj::AudioMediaPort::onFrameReceived`.
- Header PJSIP mô tả `onFrameRequested` là hook để cung cấp frame và
  `onFrameReceived` là hook nhận frame; source `media.cpp` nối chúng qua conference
  bridge.

## Giới hạn và blocker

- `COPYING` của PJSIP 2.17 là GPLv2. Chưa có quyết định pháp lý/sản phẩm cho việc
  link/vendoring vào APK; không đưa source, static library, JNI hoặc AAR vào repo.
- Chưa có JNI wrapper, Gradle module tích hợp, signaling/SIP endpoint hoặc peer B.
- Chưa có thiết bị call test và chưa chạy gate A–E: baseline, outbound substitution,
  inbound substitution, full duplex, dual-end trace.
- Android không cấp quyền tổng quát để đọc/chèn audio của app gọi điện thứ ba.
  `AudioTrack` cục bộ không phải outbound-track injection.
- Đây chỉ là feasibility evidence cho controlled VoIP do dự án sở hữu; chưa đủ để
  đóng `VT-005`, mở `VT-002/VT-004`, hoặc tuyên bố dịch voice hoạt động.

## Cách tái hiện ngoài repo

Không commit toolchain hoặc artifact GPL vào repo. Cần có NDK, CMake, Ninja và bản
source PJSIP được owner chấp thuận. Cấu hình tương đương:

```text
cmake -S <pjsip-copy> -B <build> -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=<ndk>/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-29 \
  -DBUILD_TESTING=OFF -DPJMEDIA_WITH_VIDEO=OFF
ninja -C <build> pjsua2
```

Trong spike Windows, `configure-android` cần shell tương thích để tránh NDK native
make bị nhận nhầm là Cygwin; CMake/Ninja là đường build đã chạy thành công.
