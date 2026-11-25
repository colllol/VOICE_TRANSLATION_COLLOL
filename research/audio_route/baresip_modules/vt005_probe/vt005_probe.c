/* Baresip PCM bridge filter. Callbacks never perform socket I/O. */
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <re.h>
#include <rem.h>
#include <baresip.h>

#define QUEUE_SLOTS 8
#define MAX_PCM_BYTES 8192
#define BRIDGE_MAGIC "VT08" /* mono S16LE 8000 Hz; VTB1 backend is 16000 Hz */

typedef struct bridge_lane {
    struct aufilt_enc_st enc;
    struct aufilt_dec_st dec;
    SOCKET socket_fd;
    CRITICAL_SECTION lock;
    HANDLE worker;
    HANDLE stop_event, wake_event;
    const char *port;
    int stopping;
    int active;
    uint32_t generation;
    uint8_t input[QUEUE_SLOTS][MAX_PCM_BYTES];
    uint32_t input_size[QUEUE_SLOTS];
    uint32_t input_generation[QUEUE_SLOTS];
    uint8_t output[QUEUE_SLOTS][MAX_PCM_BYTES];
    uint32_t output_size[QUEUE_SLOTS];
    uint32_t output_generation[QUEUE_SLOTS];
    unsigned input_write, input_read, output_write, output_read;
    int initialized;
} bridge_lane;

static struct aufilt filter;
static int winsock_started;

static int socket_io(bridge_lane *lane, SOCKET fd, char *data, int size, int writing)
{
    ULONGLONG deadline = GetTickCount64()+200;
    while (size > 0 && GetTickCount64() < deadline) {
        fd_set set; struct timeval tv = {0, 10000}; int n;
        if (WaitForSingleObject(lane->stop_event, 0) == WAIT_OBJECT_0) return -1;
        FD_ZERO(&set); FD_SET(fd, &set);
        n = select(0, writing ? NULL : &set, writing ? &set : NULL, NULL, &tv);
        if (n < 0) return -1;
        if (!n) continue;
        n = writing ? send(fd, data, size, 0) : recv(fd, data, size, 0);
        if (n == SOCKET_ERROR && WSAGetLastError() == WSAEWOULDBLOCK) continue;
        if (n <= 0) return -1;
        data += n; size -= n;
    }
    return size ? -1 : 0;
}

static void lane_destructor(void *arg)
{
    bridge_lane *lane = arg;
    list_unlink(&lane->enc.le);
    list_unlink(&lane->dec.le);
    if (lane->initialized) {
        EnterCriticalSection(&lane->lock);
        lane->stopping = 1;
        lane->active = 0;
        LeaveCriticalSection(&lane->lock);
        SetEvent(lane->stop_event);
        if (lane->worker) { WaitForSingleObject(lane->worker, INFINITE); CloseHandle(lane->worker); }
        CloseHandle(lane->stop_event); CloseHandle(lane->wake_event);
        DeleteCriticalSection(&lane->lock);
    }
}

static int bridge_connect(bridge_lane *lane)
{
    struct sockaddr_in address;
    SOCKET fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (fd == INVALID_SOCKET) return -1;
    u_long nb = 1;
    ioctlsocket(fd, FIONBIO, &nb);
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons((u_short)atoi(lane->port));
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (connect(fd, (struct sockaddr *)&address, sizeof(address)) == SOCKET_ERROR) {
        fd_set set; struct timeval tv = {0, 200000}; int err = 0, len = sizeof(err);
        FD_ZERO(&set); FD_SET(fd, &set);
        if (WSAGetLastError() != WSAEWOULDBLOCK || select(0, NULL, &set, NULL, &tv) <= 0 || getsockopt(fd, SOL_SOCKET, SO_ERROR, (char *)&err, &len) || err) { closesocket(fd); return -1; }
    }
    EnterCriticalSection(&lane->lock);
    if (lane->stopping) {
        LeaveCriticalSection(&lane->lock);
        closesocket(fd);
        return -1;
    }
    lane->socket_fd = fd;
    LeaveCriticalSection(&lane->lock);
    return 0;
}

static DWORD WINAPI bridge_worker(LPVOID arg)
{
    bridge_lane *lane = arg;
    HANDLE events[2] = {lane->stop_event, lane->wake_event};
    for (;;) {
        unsigned slot;
        uint32_t size, generation, wire_size;
        int stopping;
        SOCKET fd;
        uint8_t request[8 + MAX_PCM_BYTES];
        uint8_t response[8 + MAX_PCM_BYTES];
        EnterCriticalSection(&lane->lock);
        while (!lane->stopping && lane->input_read == lane->input_write) {
            LeaveCriticalSection(&lane->lock);
            if (WaitForMultipleObjects(2, events, FALSE, INFINITE) == WAIT_OBJECT_0)
                goto stopped;
            EnterCriticalSection(&lane->lock);
        }
        if (lane->stopping) {
            LeaveCriticalSection(&lane->lock);
            break;
        }
        slot = lane->input_read++ % QUEUE_SLOTS;
        size = lane->input_size[slot];
        generation = lane->input_generation[slot];
        memcpy(request + 8, lane->input[slot], size);
        LeaveCriticalSection(&lane->lock);
        EnterCriticalSection(&lane->lock);
        stopping = lane->stopping;
        fd = lane->socket_fd;
        LeaveCriticalSection(&lane->lock);
        if (stopping) break;
        if (fd == INVALID_SOCKET) {
            if (bridge_connect(lane)) continue;
            EnterCriticalSection(&lane->lock);
            fd = lane->socket_fd;
            stopping = lane->stopping;
            LeaveCriticalSection(&lane->lock);
            if (stopping) break;
            if (fd == INVALID_SOCKET) continue;
        }
        memcpy(request, BRIDGE_MAGIC, 4);
        wire_size = htonl(size);
        memcpy(request + 4, &wire_size, 4);
        if (socket_io(lane, fd, (char *)request, 8 + size, 1)
            || socket_io(lane, fd, (char *)response, 8, 0)) {
            EnterCriticalSection(&lane->lock);
            if (lane->socket_fd == fd) lane->socket_fd = INVALID_SOCKET;
            LeaveCriticalSection(&lane->lock);
            closesocket(fd);
            EnterCriticalSection(&lane->lock);
            stopping = lane->stopping;
            lane->input_read = lane->input_write;
            lane->output_read = lane->output_write;
            LeaveCriticalSection(&lane->lock);
            if (stopping) break;
            continue;
        }
        memcpy(&wire_size, response + 4, 4);
        size = ntohl(wire_size);
        if (memcmp(response, BRIDGE_MAGIC, 4) || size > MAX_PCM_BYTES
            || socket_io(lane, fd, (char *)response + 8, (int)size, 0)) {
            EnterCriticalSection(&lane->lock);
            if (lane->socket_fd == fd) lane->socket_fd = INVALID_SOCKET;
            LeaveCriticalSection(&lane->lock);
            closesocket(fd);
            EnterCriticalSection(&lane->lock);
            stopping = lane->stopping;
            lane->input_read = lane->input_write;
            lane->output_read = lane->output_write;
            LeaveCriticalSection(&lane->lock);
            if (stopping) break;
            continue;
        }
        EnterCriticalSection(&lane->lock);
        if (lane->stopping) {
            LeaveCriticalSection(&lane->lock);
            break;
        }
        if (lane->active && lane->generation == generation) {
            unsigned out = lane->output_write++ % QUEUE_SLOTS;
            memcpy(lane->output[out], response + 8, size);
            lane->output_size[out] = size;
            lane->output_generation[out] = generation;
            if (lane->output_write - lane->output_read > QUEUE_SLOTS)
                lane->output_read = lane->output_write - QUEUE_SLOTS;
        }
        LeaveCriticalSection(&lane->lock);
    }
    if (lane->socket_fd != INVALID_SOCKET) closesocket(lane->socket_fd);
    lane->socket_fd = INVALID_SOCKET;
    return 0;
stopped:
    if (lane->socket_fd != INVALID_SOCKET) closesocket(lane->socket_fd);
    lane->socket_fd = INVALID_SOCKET;
    return 0;
}

static int lane_ready(bridge_lane *lane, const char *port)
{
    if (lane->initialized) return 0;
    lane->port = port; lane->socket_fd = INVALID_SOCKET; lane->generation = 1;
    InitializeCriticalSection(&lane->lock);
    lane->stop_event = CreateEvent(NULL, TRUE, FALSE, NULL);
    lane->wake_event = CreateEvent(NULL, FALSE, FALSE, NULL);
    if (!lane->stop_event || !lane->wake_event) {
        if (lane->stop_event) CloseHandle(lane->stop_event);
        if (lane->wake_event) CloseHandle(lane->wake_event);
        DeleteCriticalSection(&lane->lock); return ENOMEM;
    }
    lane->initialized = 1;
    lane->worker = CreateThread(NULL, 0, bridge_worker, lane, 0, NULL);
    if (!lane->worker) {
        lane->initialized = 0; CloseHandle(lane->stop_event); CloseHandle(lane->wake_event);
        DeleteCriticalSection(&lane->lock); return ENOMEM;
    }
    lane->active = 1; return 0;
}

static int lane_frame(bridge_lane *lane, struct auframe *frame)
{
    uint32_t bytes, generation;
    unsigned in_slot;
    if (!frame->sampv) return EINVAL;
    bytes = (uint32_t)(frame->sampc * sizeof(int16_t));
    if (!TryEnterCriticalSection(&lane->lock)) { memset(frame->sampv, 0, bytes); return 0; }
    if (!lane->active) {
        memset(frame->sampv, 0, bytes);
        LeaveCriticalSection(&lane->lock);
        return 0;
    }
    if (frame->fmt != AUFMT_S16LE || frame->srate != 8000 || frame->ch != 1 || !frame->sampv || !frame->sampc) {
        if (frame->sampv) memset(frame->sampv, 0, frame->sampc * sizeof(int16_t));
        LeaveCriticalSection(&lane->lock);
        return 0;
    }
    bytes = (uint32_t)(frame->sampc * sizeof(int16_t));
    if (bytes > MAX_PCM_BYTES) {
        memset(frame->sampv, 0, bytes);
        LeaveCriticalSection(&lane->lock);
        return 0;
    }
    if (lane->input_write - lane->input_read < QUEUE_SLOTS) {
        generation = lane->generation;
        in_slot = lane->input_write++ % QUEUE_SLOTS;
        memcpy(lane->input[in_slot], frame->sampv, bytes);
        lane->input_size[in_slot] = bytes;
        lane->input_generation[in_slot] = generation;
        SetEvent(lane->wake_event);
    }
    if (lane->output_read != lane->output_write) {
        unsigned out = lane->output_read++ % QUEUE_SLOTS;
        if (lane->output_generation[out] == lane->generation) {
            uint32_t copy = lane->output_size[out] < bytes ? lane->output_size[out] : bytes;
            memcpy(frame->sampv, lane->output[out], copy);
            if (copy < bytes) memset((uint8_t *)frame->sampv + copy, 0, bytes - copy);

        }
        else memset(frame->sampv, 0, bytes);
    }
    else memset(frame->sampv, 0, bytes);
    LeaveCriticalSection(&lane->lock);
    return 0;
}

static int tx_setup(struct aufilt_enc_st **state, void **ctx, const struct aufilt *af,
                    struct aufilt_prm *params, const struct audio *audio)
{
    (void)ctx; (void)af; (void)params; (void)audio;
    if (!*state) *state = mem_zalloc(sizeof(bridge_lane), lane_destructor);
    if (!*state) return ENOMEM;
    return lane_ready((bridge_lane *)*state, "19091");
}

static int rx_setup(struct aufilt_dec_st **state, void **ctx, const struct aufilt *af,
                    struct aufilt_prm *params, const struct audio *audio)
{
    (void)ctx; (void)af; (void)params; (void)audio;
    if (!*state) *state = mem_zalloc(sizeof(bridge_lane), lane_destructor);
    if (!*state) return ENOMEM;
    return lane_ready((bridge_lane *)*state, "19092");
}

static int tx_replace(struct aufilt_enc_st *state, struct auframe *frame)
{
    return lane_frame((bridge_lane *)state, frame);
}

static int rx_replace(struct aufilt_dec_st *state, struct auframe *frame)
{
    return lane_frame((bridge_lane *)state, frame);
}

static struct aufilt filter = { .name = "vt005_probe", .encupdh = tx_setup,
    .ench = tx_replace, .decupdh = rx_setup, .dech = rx_replace };

static int probe_init(void)
{
    WSADATA data;
    if (WSAStartup(MAKEWORD(2, 2), &data)) return ENODEV;
    winsock_started = 1;
    aufilt_register(baresip_aufiltl(), &filter);
    return 0;
}

static int probe_close(void)
{
    aufilt_unregister(&filter);
    if (winsock_started) WSACleanup();
    return 0;
}

EXPORT_SYM const struct mod_export DECL_EXPORTS(vt005_probe) = {
    "vt005_probe", "filter", probe_init, probe_close,
};
