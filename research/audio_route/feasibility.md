# VT-005 â€” kiá»ƒm chá»©ng Ä‘iá»ƒm tÃ­ch há»£p VoIP trÃªn thiáº¿t bá»‹ A

Cáº­p nháº­t: 2026-10-13. **ChÆ°a gá»i VoIP tháº­t / chÆ°a nghiá»‡m thu trÃªn Redmi K70.**
Chá»‰ A cÃ i/Ä‘iá»u khiá»ƒn cÃ´ng cá»¥; B dÃ¹ng VoIP bÃ¬nh thÆ°á»ng, khÃ´ng cÃ i cÃ´ng cá»¥ dá»‹ch.

## Ranh giá»›i thá»±c táº¿

- Vá»›i app gá»i bÃªn thá»© ba khÃ´ng cung cáº¥p audio callback hoáº·c plugin há»£p lá»‡, Android khÃ´ng cáº¥p quyá»n tá»•ng quÃ¡t Ä‘á»ƒ Ä‘á»c hai track vÃ  chÃ¨n TTS thay mic. USB debugging khÃ´ng cáº¥p quyá»n nÃ y.
- Vertical slice cáº§n A sá»Ÿ há»¯u Ä‘iá»ƒm tÃ­ch há»£p trÆ°á»›c encoder gá»­i Ä‘i vÃ  sau decoder nháº­n vá». B cáº§n má»™t client VoIP *tÆ°Æ¡ng thÃ­ch cuá»™c gá»i*, khÃ´ng cáº§n cÃ i app dá»‹ch; khÃ´ng há»©a B dÃ¹ng app gá»i báº¥t ká»³ khÃ´ng tÆ°Æ¡ng thÃ­ch giao thá»©c.
- `AudioRecord` thu mic A; `AudioTrack` chá»‰ phÃ¡t cá»¥c bá»™ á»Ÿ A, **khÃ´ng** Ä‘Æ°a báº£n dá»‹ch vÃ o outbound call. B pháº£i nghe qua RTP/track cá»§a VoIP Ä‘á»ƒ Ä‘áº¡t gate.
- PJSIP/PJSUA2 lÃ  má»™t á»©ng viÃªn chá»© chÆ°a Ä‘Æ°á»£c chá»n. TÃ i liá»‡u nÃªu `AudioMediaPort.onFrameRequested/onFrameReceived` vÃ  conference bridge cho Ä‘Æ°á»ng media. Cáº§n spike native/JNI trÃªn Android A Ä‘á»ƒ xÃ¡c nháº­n thá»© tá»± send/receive vÃ  clock domain; khÃ´ng giáº£ Ä‘á»‹nh API C++ tá»± tÃ­ch há»£p Kotlin.
  Nguá»“n Ä‘Ã£ xem: https://docs.pjsip.org/en/latest/api/generated/pjsip/group/group__PJSUA2__MED.html vÃ  https://docs.pjsip.org/en/latest/pjsua2/using/media_audio.html (2026-10-13).

## ÄÆ°á»ng Ã¢m thanh má»¥c tiÃªu

1. Aâ†’B: mic A â†’ AudioRecord/VoIP capture táº¡i A â†’ pipeline dá»‹ch â†’ **thay audio outbound trÆ°á»›c encoder** â†’ VoIP network â†’ B nghe voice dá»‹ch. Mute/bá» qua mic gá»‘c trÃªn outbound lÃºc dá»‹ch Ä‘á»ƒ B khÃ´ng nghe láº«n.
2. Bâ†’A: B nÃ³i qua client VoIP â†’ VoIP decode táº¡i A â†’ láº¥y audio B trÆ°á»›c render â†’ pipeline dá»‹ch â†’ AudioTrack/VoIP render á»Ÿ A â†’ A nghe voice dá»‹ch. Cháº·n audio B gá»‘c khá»i render song song náº¿u báº­t cháº¿ Ä‘á»™ dá»‹ch.
3. Hai pipeline cÃ³ `direction`, `seq`, phiÃªn vÃ  hÃ ng Ä‘á»£i riÃªng; `stop` xÃ³a buffer, trÃ¡nh láº·p/echo. KhÃ´ng buá»™c B xÃ¡c nháº­n trÃªn á»©ng dá»¥ng dá»‹ch.

## Gate cháº¡y trÃªn thiáº¿t bá»‹ tháº­t

A. Baseline VoIP: gá»i A/B, xÃ¡c minh mic/loa gá»‘c hai phÃ­a vÃ  codec/sample rate.
B. Outbound substitution: bÆ¡m fixture PCM Ä‘Æ°á»£c phÃ©p vÃ o **outbound track**, giá»¯ mic A im láº·ng; B nghe vÃ  ghi nháº­n Ä‘Ãºng fixture qua cuá»™c gá»i, khÃ´ng nghe mic A gá»‘c.
C. Inbound substitution: B gá»­i fixture qua cuá»™c gá»i; A nháº­n táº¡i hook trÆ°á»›c render, thay báº±ng fixture nháº­n Ä‘Æ°á»£c/processed; A nghe Ä‘Ãºng báº£n Ä‘Ã£ thay, khÃ´ng nghe báº£n gá»‘c.
D. Full duplex: cáº£ hai nÃ³i gáº§n Ä‘á»“ng thá»i; kiá»ƒm riÃªng hÆ°á»›ng, thá»© tá»±, echo, stop/reconnect vÃ  stale frame.
E. Thu trace cÃ³ consent táº¡i hai Ä‘áº§u hoáº·c checksum/frame count/timestamp Ä‘á»§ chá»©ng minh, khÃ´ng Ä‘Æ°a audio cÃ¡ nhÃ¢n vÃ o git/vault.

`research/audio_route/test_route.py` chá»‰ thá»­ router/fake send-render Ä‘á»ƒ báº¯t lá»—i phÃ¢n luá»“ng, **khÃ´ng** chá»©ng minh native VoIP hoáº·c Android Ä‘Ã£ káº¿t ná»‘i.

## Tráº¡ng thÃ¡i mÃ´i trÆ°á»ng

`adb devices -l` vÃ  `adb mdns services` trá»‘ng sau khi restart ADB. áº¢nh Ä‘iá»‡n thoáº¡i Redmi K70 cho tháº¥y báº­t USB/Wireless debugging; PC cÃ¹ng subnet vÃ  port Wi-Fi trÃªn áº£nh má»Ÿ TCP nhÆ°ng chÆ°a pair. `adb connect` chÆ°a thÃ nh cÃ´ng. ChÆ°a cÃ³ SDK PJSIP trong repo, chÆ°a cÃ³ second peer/test call.

Muá»‘n káº¿t ná»‘i ADB qua Wi-Fi: trÃªn Ä‘iá»‡n thoáº¡i má»Ÿ *Pair device with pairing code*, láº¥y Ä‘á»‹a chá»‰ pairing `IP:port`; trÃªn chÃ­nh mÃ¡y tÃ­nh gÃµ `adb pair IP:port`, nháº­p mÃ£ sÃ¡u sá»‘ trong terminal riÃªng, khÃ´ng dÃ¡n mÃ£ vÃ o chat hoáº·c commit. Sau bÃ¡o thÃ nh cÃ´ng cháº¡y `adb connect` vá»›i **IP:port cá»§a trang Wireless debugging**, rá»“i `adb devices -l`; má»™t sá»‘ port Ä‘á»•i sau restart. Náº¿u USB: dÃ¹ng cÃ¡p dá»¯ liá»‡u, chá»n File transfer/MTP, cháº¥p nháº­n há»™p thoáº¡i RSA trÃªn Ä‘iá»‡n thoáº¡i, kiá»ƒm driver Android ADB trong Windows Device Manager.