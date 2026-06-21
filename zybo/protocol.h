/*
 * market-lab wire protocol — Zybo PS side
 *
 * The simulator sends QUOTE frames over UDP and accepts ORDER frames
 * over TCP.  All fields are big-endian (network byte order); the Zynq
 * ARM core is little-endian, so use ntohl/htonl on every multi-byte field.
 *
 * Data flow:
 *   PC ──[UDP QUOTE 28 B]──► Zybo   (bind UDP socket on FEED_PORT)
 *   PC ◄─[TCP ORDER 18 B]── Zybo   (TCP connect to PC:OMS_PORT)
 *   PC ──[TCP FILL  14 B]──► Zybo   (same TCP connection)
 */

#ifndef MARKET_LAB_PROTOCOL_H
#define MARKET_LAB_PROTOCOL_H

#include <stdint.h>
#include <arpa/inet.h>   /* ntohl, ntohs, htonl, htons */

/* ── Ports (match config.py) ─────────────────────────────────────────── */
#define FEED_PORT  5000   /* UDP — bind here to receive quotes          */
#define OMS_PORT   5001   /* TCP — connect here to send orders          */

/* ── Message type tags ───────────────────────────────────────────────── */
#define MSG_QUOTE      0x01
#define MSG_TRADE      0x02
#define MSG_NEW_ORDER  0x10
#define MSG_FILL       0x20

/* ── Side / order type / status constants ────────────────────────────── */
#define SIDE_BUY        0
#define SIDE_SELL       1

#define ORD_MARKET      0
#define ORD_LIMIT       1

#define STATUS_FILLED   0
#define STATUS_PARTIAL  1
#define STATUS_REJECTED 2

/* ── Fixed-point price encoding ──────────────────────────────────────── */
/*    wire value = round(price * 10000)  →  $470.12 is stored as 4701200 */
#define PRICE_SCALE     10000u

static inline float    px_decode(uint32_t px_be) { return (float)ntohl(px_be) / PRICE_SCALE; }
static inline uint32_t px_encode(float price)     { return htonl((uint32_t)(price * PRICE_SCALE + 0.5f)); }

/* ── Wire frames ─────────────────────────────────────────────────────── */

/*
 * QUOTE  — 28 bytes, received over UDP from the simulator feed.
 * Unpack all multi-byte fields with ntohl / be64toh before use.
 */
typedef struct __attribute__((packed)) {
    uint8_t  msg_type;   /* MSG_QUOTE = 0x01                    */
    uint8_t  sym_id;     /* 0 = QQQ                             */
    uint16_t _pad;
    uint64_t ts_us;      /* microseconds since Unix epoch (BE)  */
    uint32_t bid_px;     /* bid price  × 10000, big-endian      */
    uint32_t ask_px;     /* ask price  × 10000, big-endian      */
    uint32_t bid_sz;     /* bid size (shares), big-endian       */
    uint32_t ask_sz;     /* ask size (shares), big-endian       */
} quote_frame_t;         /* sizeof = 28                         */

/*
 * ORDER  — 18 bytes, sent over TCP to the simulator OMS.
 * Fill all multi-byte fields with htonl before sending.
 */
typedef struct __attribute__((packed)) {
    uint8_t  msg_type;   /* MSG_NEW_ORDER = 0x10                */
    uint8_t  sym_id;     /* 0 = QQQ                             */
    uint8_t  side;       /* SIDE_BUY / SIDE_SELL                */
    uint8_t  order_type; /* ORD_MARKET / ORD_LIMIT              */
    uint32_t order_id;   /* your sequence number, big-endian    */
    uint32_t qty;        /* shares, big-endian                  */
    uint32_t limit_px;   /* 0 for market orders, big-endian     */
    uint16_t _pad;
} order_frame_t;         /* sizeof = 18                         */

/*
 * FILL   — 14 bytes, received over TCP after submitting an order.
 */
typedef struct __attribute__((packed)) {
    uint8_t  msg_type;   /* MSG_FILL = 0x20                     */
    uint8_t  status;     /* STATUS_FILLED / REJECTED / PARTIAL  */
    uint32_t order_id;   /* echoes your order_id, big-endian    */
    uint32_t fill_qty;   /* shares filled, big-endian           */
    uint32_t fill_px;    /* fill price × 10000, big-endian      */
} fill_frame_t;          /* sizeof = 14                         */

/* ── Compile-time size assertions ────────────────────────────────────── */
_Static_assert(sizeof(quote_frame_t) == 28, "quote_frame_t must be 28 bytes");
_Static_assert(sizeof(order_frame_t) == 18, "order_frame_t must be 18 bytes");
_Static_assert(sizeof(fill_frame_t)  == 14, "fill_frame_t must be 14 bytes");

#endif /* MARKET_LAB_PROTOCOL_H */
