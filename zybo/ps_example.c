/*
 * ps_example.c — minimal Zybo PS skeleton for market-lab
 *
 * Compile on Zybo (baremetal or Linux):
 *   arm-linux-gnueabihf-gcc -o ps_example ps_example.c
 *
 * Replace PC_IP with your development machine's IP address.
 * The PL interface (AXI registers, interrupts) is left as TODO —
 * this file proves out the network plumbing first.
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#include "protocol.h"

#define PC_IP   "192.168.1.100"   /* ← your machine running run.py */

/* ── UDP feed socket ─────────────────────────────────────────────────── */
static int open_feed_socket(void) {
    int sock = socket(AF_INET, SOCK_DGRAM, 0);

    struct sockaddr_in addr = {
        .sin_family      = AF_INET,
        .sin_port        = htons(FEED_PORT),
        .sin_addr.s_addr = INADDR_ANY,   /* receive on all interfaces */
    };
    bind(sock, (struct sockaddr *)&addr, sizeof(addr));
    return sock;
}

/* ── TCP OMS socket ──────────────────────────────────────────────────── */
static int open_oms_socket(void) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_port   = htons(OMS_PORT),
    };
    inet_pton(AF_INET, PC_IP, &addr.sin_addr);
    connect(sock, (struct sockaddr *)&addr, sizeof(addr));
    return sock;
}

/* ── Send one order ──────────────────────────────────────────────────── */
static uint32_t order_seq = 1;

static void send_order(int oms_sock, uint8_t side, uint8_t ord_type,
                       uint32_t qty, float limit_price) {
    order_frame_t frame = {
        .msg_type   = MSG_NEW_ORDER,
        .sym_id     = 0,
        .side       = side,
        .order_type = ord_type,
        .order_id   = htonl(order_seq++),
        .qty        = htonl(qty),
        .limit_px   = px_encode(limit_price),
        ._pad       = 0,
    };
    send(oms_sock, &frame, sizeof(frame), 0);
}

/* ── Receive one fill ────────────────────────────────────────────────── */
static int recv_fill(int oms_sock, fill_frame_t *out) {
    uint8_t buf[sizeof(fill_frame_t)];
    int n = 0;
    while (n < (int)sizeof(fill_frame_t)) {
        int r = recv(oms_sock, buf + n, sizeof(fill_frame_t) - n, 0);
        if (r <= 0) return -1;
        n += r;
    }
    memcpy(out, buf, sizeof(fill_frame_t));
    return 0;
}

/* ── Main loop ───────────────────────────────────────────────────────── */
int main(void) {
    int feed_sock = open_feed_socket();
    int oms_sock  = open_oms_socket();
    printf("Connected to market-lab at %s\n", PC_IP);

    uint8_t buf[sizeof(quote_frame_t)];

    while (1) {
        /* 1. Block until next QUOTE frame arrives over UDP */
        ssize_t n = recv(feed_sock, buf, sizeof(buf), 0);
        if (n != sizeof(quote_frame_t)) continue;

        quote_frame_t *q = (quote_frame_t *)buf;
        if (q->msg_type != MSG_QUOTE) continue;

        float bid = px_decode(q->bid_px);
        float ask = px_decode(q->ask_px);
        printf("QUOTE  bid=%.4f  ask=%.4f  spread=%.4f\n",
               bid, ask, ask - bid);

        /* 2. TODO: pass bid/ask to PL via AXI registers, read back signal
         *    uint32_t signal = Xil_In32(PL_SIGNAL_ADDR);  */
        uint32_t signal = 0;   /* placeholder — replace with PL read */

        /* 3. Act on PL output */
        if (signal == 1) {
            send_order(oms_sock, SIDE_BUY, ORD_MARKET, 100, 0.0f);

            fill_frame_t fill;
            if (recv_fill(oms_sock, &fill) == 0) {
                float fill_px = px_decode(fill.fill_px);
                printf("FILL   id=%u  status=%u  qty=%u  px=%.4f\n",
                       ntohl(fill.order_id), fill.status,
                       ntohl(fill.fill_qty), fill_px);
            }
        }
    }
}
