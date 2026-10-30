

#ifndef SHARED_CORRIDOR_H
#define SHARED_CORRIDOR_H

/*
=========================================================
 SMART AMBULANCE GREEN CORRIDOR (SAGC)
 Common Interface Header - Version 1.0

 Hardware : Raspberry Pi 4B
 OS       : QNX SDP 8.0
 Language : C

 SIX PROJECT BLOCKS:
 P1 - Ambulance Simulator
 P2 - Ingestion and Validation
 P3 - Watchdog and Fault Monitor
 P4 - Intelligent Corridor Controller
 P5 - Traffic Signal Output
 P6 - Monitoring Dashboard

 IMPORTANT:
 All members must use this same header.
 Do not create separate copies of the structures.
=========================================================
*/

#include <stdint.h>
#include <string.h>


/* =====================================================
   1. COMMON CONFIGURATION
   ===================================================== */

/* Version number of the SAGC communication protocol */
#define SAGC_PROTOCOL_VERSION 1

/* Final demonstration supports four traffic junctions */
#define SAGC_MAX_JUNCTIONS 4

/* HMAC-SHA256 produces a 32-byte authentication tag */
#define SAGC_HMAC_SIZE 32


/* =====================================================
   2. TIMING CONFIGURATION
   ===================================================== */

/* P2 and P4 send heartbeat messages every 500 ms */
#define SAGC_HEARTBEAT_INTERVAL_MS 500

/* P3 detects a missing heartbeat after 2 seconds */
#define SAGC_WATCHDOG_TIMEOUT_MS 2000

/* P1 sends ambulance GPS updates every 500 ms */
#define SAGC_PACKET_SEND_INTERVAL_MS 500

/* Maximum time without a valid ambulance packet */
#define SAGC_PACKET_STALE_MS 2000

/* Maximum permitted packet timestamp difference */
#define SAGC_MAX_TIMESTAMP_SKEW_MS 1000

/* P5 detects missing signal commands after 2 seconds */
#define SAGC_P5_COMMAND_TIMEOUT_MS 2000


/* =====================================================
   3. GEOFENCE AND ETA CONFIGURATION
   ===================================================== */

/* Initial geofence radius around a junction */
#define SAGC_GEOFENCE_RADIUS_M 500

/* Ambulance green should be active by this ETA */
#define SAGC_ETA_THRESHOLD_SEC 30

/* Initial simulated yellow-light duration */
#define SAGC_YELLOW_MS 3000

/* Initial simulated all-red clearance duration */
#define SAGC_ALL_RED_MS 2000

/* Preparation must begin early enough to complete
   yellow and all-red phases before ambulance arrival */
#define SAGC_PREPARE_LEAD_SEC \
    ((SAGC_YELLOW_MS + SAGC_ALL_RED_MS) / 1000)

/* Example: preparation starts when ETA reaches 35 sec */
#define SAGC_PREPARE_ETA_SEC \
    (SAGC_ETA_THRESHOLD_SEC + SAGC_PREPARE_LEAD_SEC)


/* =====================================================
   4. NETWORK CONFIGURATION
   ===================================================== */

/* P2 receives ambulance requests from P1 on this port */
#define SAGC_UDP_PORT_AMBULANCE 5000

/* P1 receives test commands from P6 on this port */
#define SAGC_UDP_PORT_FAULT_INJECT 5001


/* =====================================================
   5. QNX IPC RECEIVER NAMES
   ===================================================== */

/* Names used by QNX name_attach() for internal processes */

#define SAGC_NAME_P3_WATCHDOG "sagc_p3"
#define SAGC_NAME_P4_CONTROLLER "sagc_p4"
#define SAGC_NAME_P5_SIGNAL "sagc_p5"
#define SAGC_NAME_P6_DASHBOARD "sagc_p6"


/* =====================================================
   6. MESSAGE TYPES
   ===================================================== */

/* Identifies the type of message being communicated */

typedef enum
{
    MSG_AMBULANCE_REQUEST = 1,
    MSG_EMERGENCY_REQUEST,
    MSG_HEARTBEAT,
    MSG_FAULT_ALERT,
    MSG_SIGNAL_COMMAND,
    MSG_SIGNAL_FEEDBACK,
    MSG_SYSTEM_STATUS

} SagcMessageType;


/* =====================================================
   7. PROCESS IDENTIFIERS
   ===================================================== */

/* Identifies which SAGC process is sending a message */

typedef enum
{
    PROCESS_P1_AMBULANCE = 1,
    PROCESS_P2_INGESTION,
    PROCESS_P3_WATCHDOG,
    PROCESS_P4_CONTROLLER,
    PROCESS_P5_SIGNAL,
    PROCESS_P6_DASHBOARD

} SagcProcessID;


/* =====================================================
   8. TRAFFIC SIGNAL STATES
   ===================================================== */

/* Represents the signal displayed at each direction */

typedef enum
{
    SIGNAL_RED = 0,
    SIGNAL_YELLOW,
    SIGNAL_GREEN,
    SIGNAL_FLASH_AMBER

} SignalState;


/* =====================================================
   9. CORRIDOR STATES
   ===================================================== */

/* P4 uses these states to control the traffic corridor */

typedef enum
{
    CORRIDOR_NORMAL = 0,
    CORRIDOR_PREPARING,
    CORRIDOR_ALL_RED,
    CORRIDOR_AMBULANCE_GREEN,
    CORRIDOR_CLEARING,
    CORRIDOR_FLASH_AMBER

} CorridorState;


/* =====================================================
   10. FAULT TYPES
   ===================================================== */

/* Identifies the fault detected by P2, P3 or P5 */

typedef enum
{
    FAULT_NONE = 0,
    FAULT_P2_TIMEOUT,
    FAULT_P4_TIMEOUT,
    FAULT_INVALID_PACKET,
    FAULT_AUTHENTICATION_FAILED,
    FAULT_REPLAY_DETECTED,
    FAULT_GPS_UNAVAILABLE,
    FAULT_NO_VALID_PACKET,
    FAULT_SIGNAL_OUTPUT_FAILED

} SagcFaultCode;


/* Fault severity levels */

#define SAGC_SEVERITY_INFO       1
#define SAGC_SEVERITY_DEGRADE    2
#define SAGC_SEVERITY_CRITICAL   3


/* =====================================================
   11. FAULT INJECTION TYPES
   ===================================================== */

/* Test commands used by the P6 dashboard to test P1 */

typedef enum
{
    INJECT_NONE = 0,
    INJECT_GPS_LOSS,
    INJECT_BAD_MAC,
    INJECT_REPLAY,
    INJECT_PACKET_DELAY,
    INJECT_PACKET_LOSS,
    INJECT_CLEAR_ALL

} FaultInjectType;


/* =====================================================
   12. AMBULANCE REQUEST
   P1 -> P2 THROUGH UDP
   ===================================================== */

/* Session-ending flag indicates that the ambulance
   has completed its simulated journey */

#define SAGC_FLAG_SESSION_END 0x01

/* Logical representation of ambulance information.
   This structure is converted to a fixed UDP format.
   Do not transmit this structure directly as raw bytes. */

typedef struct
{
    uint8_t protocol_version;

    /* Emergency priority:
       1 = highest priority
       5 = lowest priority */
    uint8_t triage_level;

    /* Additional request flags */
    uint8_t flags;

    uint32_t ambulance_id;

    /* Increases with every new ambulance packet */
    uint32_t sequence_number;

    /* GPS coordinates stored in microdegrees */
    int32_t latitude;
    int32_t longitude;

    /* Ambulance speed in kilometres per hour */
    uint16_t speed_kmph;

    /* Timestamp from CLOCK_MONOTONIC, in milliseconds */
    uint64_t timestamp_ms;

    /* Authentication tag generated using HMAC-SHA256 */
    uint8_t auth_tag[SAGC_HMAC_SIZE];

} AmbulanceRequest;


/* =====================================================
   13. VALIDATED EMERGENCY REQUEST
   P2 -> P4 THROUGH QNX IPC
   ===================================================== */

/* P2 creates this structure only after validating
   the received ambulance request */

typedef struct
{
    uint32_t ambulance_id;
    uint32_t sequence_number;

    int32_t latitude;
    int32_t longitude;

    uint16_t speed_kmph;

    uint8_t triage_level;
    uint8_t flags;

    /* Time at which P2 received the valid request */
    uint64_t received_time_ms;

    /* Indicates successful authentication */
    uint8_t authenticated;

    /* Indicates whether GPS information is valid */
    uint8_t gps_valid;

} EmergencyRequest;


/* =====================================================
   14. HEARTBEAT MESSAGE
   P2/P4 -> P3
   ===================================================== */

/* P2 and P4 periodically send heartbeat messages.
   P3 uses them to detect silent or failed processes. */

typedef struct
{
    uint32_t process_id;

    uint32_t sequence_number;

    uint64_t timestamp_ms;

    /* 1 = healthy, 0 = unhealthy */
    uint8_t process_healthy;

    /* Cumulative rejected packet count, filled by P2 */
    uint32_t rejected_packets;

} HeartbeatMessage;


/* =====================================================
   15. FAULT NOTIFICATION
   P3 -> P4
   ===================================================== */

/* P3 sends this message when a monitored process
   misses its heartbeat or another monitored fault occurs. */

typedef struct
{
    uint32_t source_process_id;

    SagcFaultCode fault_code;

    uint64_t timestamp_ms;

    /* Uses SAGC_SEVERITY_* values */
    uint8_t severity;

    /* Optional diagnostic information */
    uint32_t detail;

} FaultMessage;


/* =====================================================
   16. SIGNAL COMMAND
   P4 -> P5
   ===================================================== */

/* P4 sends the desired traffic signal states
   for one particular junction. */

typedef struct
{
    /* J1 = 1, J2 = 2, J3 = 3, J4 = 4 */
    uint32_t junction_id;

    /* Signal states for four approaches */
    SignalState north;
    SignalState south;
    SignalState east;
    SignalState west;

    /* Current corridor state */
    CorridorState corridor_state;

    /* Unique command number */
    uint32_t command_sequence;

    uint64_t timestamp_ms;

} SignalCommand;


/* =====================================================
   17. SIGNAL FEEDBACK
   P5 -> P4
   ===================================================== */

/* P5 reports whether the requested signal state
   was successfully applied. */

typedef struct
{
    uint32_t junction_id;

    SignalState north;
    SignalState south;
    SignalState east;
    SignalState west;

    /* Identifies the command being acknowledged */
    uint32_t command_sequence;

    /* 1 = applied, 0 = failed */
    uint8_t command_applied;

    /* Time between command receipt and output change */
    uint32_t switch_latency_us;

    uint64_t timestamp_ms;

} SignalFeedback;


/* =====================================================
   18. JUNCTION INFORMATION
   ===================================================== */

/* Stores the location and availability of each junction */

typedef struct
{
    uint32_t junction_id;

    int32_t latitude;
    int32_t longitude;

    /* 1 = active, 0 = inactive */
    uint8_t is_active;

} JunctionInfo;


/* =====================================================
   19. INDIVIDUAL JUNCTION STATUS
   P4 -> P6
   ===================================================== */

/* Stores the current status of one junction */

typedef struct
{
    uint32_t junction_id;

    CorridorState state;

    uint32_t eta_seconds;

    /* 1 = ambulance detected, 0 = not detected */
    uint8_t ambulance_detected;

} JunctionStatus;


/* =====================================================
   20. COMPLETE CORRIDOR STATUS
   P4 -> P6
   ===================================================== */

/* Carries the status of all four junctions to the
   monitoring dashboard. */

typedef struct
{
    uint32_t ambulance_id;

    uint8_t triage_level;

    /* Number of junctions currently configured */
    uint32_t junction_count;

    /* Status of J1, J2, J3 and J4 */
    JunctionStatus junctions[SAGC_MAX_JUNCTIONS];

    uint8_t fault_active;

    SagcFaultCode current_fault;

    uint32_t rejected_packets;

    uint32_t last_switch_latency_us;

    uint64_t timestamp_ms;

} SystemStatus;


/* =====================================================
   21. FAULT INJECTION COMMAND
   P6 -> P1 THROUGH UDP
   ===================================================== */

/* P6 uses this command to test GPS loss, bad MAC,
   replayed packets and other simulated faults. */

typedef struct
{
    FaultInjectType inject_type;

    /* Duration of the test in milliseconds.
       Zero means until INJECT_CLEAR_ALL. */
    uint32_t duration_ms;

    uint32_t command_sequence;

    uint64_t timestamp_ms;

} FaultInjectCommand;


/* =====================================================
   22. INTERNAL QNX IPC MESSAGE
   ===================================================== */

/* Common container for communication between
   the internal QNX processes.

   The receiver checks message_type before reading
   the corresponding union member. */

typedef struct
{
    SagcMessageType message_type;

    uint32_t sender_process_id;

    union
    {
        EmergencyRequest emergency_request;

        HeartbeatMessage heartbeat;

        FaultMessage fault;

        SignalCommand signal_command;

        SignalFeedback signal_feedback;

        SystemStatus system_status;

    } data;

} SagcIpcMessage;


/* QNX IPC reply status values */

#define SAGC_REPLY_OK       0
#define SAGC_REPLY_REJECTED 1


/* Reply structure used by QNX MsgSend/MsgReceive */

typedef struct
{
    uint32_t status;

} SagcIpcReply;


/* =====================================================
   23. UDP AMBULANCE PACKET FORMAT
   P1 -> P2
   ===================================================== */

/*
   Fixed UDP packet size: 64 bytes.

   All multi-byte fields use BIG-ENDIAN byte order.

   BYTE OFFSET   FIELD
   ------------------------------------
   0             Protocol version
   1             Triage level
   2             Flags
   3             Reserved
   4 - 7         Ambulance ID
   8 - 11        Sequence number
   12 - 15       Latitude
   16 - 19       Longitude
   20 - 21       Speed
   22 - 23       Reserved
   24 - 31       Timestamp
   32 - 63       HMAC authentication tag

   HMAC-SHA256 is calculated over bytes 0-31.
*/

#define SAGC_WIRE_PACKET_SIZE 64

#define SAGC_WIRE_AUTH_OFFSET 32


/* =====================================================
   24. BYTE ENCODING FUNCTIONS
   ===================================================== */

/* Converts a 16-bit number into big-endian bytes */

static inline void sagc_put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v >> 8);
    p[1] = (uint8_t)v;
}


/* Converts a 32-bit number into big-endian bytes */

static inline void sagc_put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}


/* Converts a 64-bit number into big-endian bytes */

static inline void sagc_put_u64(uint8_t *p, uint64_t v)
{
    sagc_put_u32(p, (uint32_t)(v >> 32));
    sagc_put_u32(p + 4, (uint32_t)v);
}


/* Reads a 16-bit big-endian number */

static inline uint16_t sagc_get_u16(const uint8_t *p)
{
    return (uint16_t)(((uint16_t)p[0] << 8) | p[1]);
}


/* Reads a 32-bit big-endian number */

static inline uint32_t sagc_get_u32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) |
           ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) |
           (uint32_t)p[3];
}


/* Reads a 64-bit big-endian number */

static inline uint64_t sagc_get_u64(const uint8_t *p)
{
    return ((uint64_t)sagc_get_u32(p) << 32) |
            sagc_get_u32(p + 4);
}


/* =====================================================
   25. UDP ENCODING FUNCTION
   ===================================================== */

/* Converts AmbulanceRequest into the fixed 64-byte
   UDP format.

   The caller must calculate the HMAC tag first
   and store it in auth_tag. */

static inline void sagc_encode_request(
    const AmbulanceRequest *r,
    uint8_t buf[SAGC_WIRE_PACKET_SIZE])
{
    buf[0] = r->protocol_version;
    buf[1] = r->triage_level;
    buf[2] = r->flags;
    buf[3] = 0;

    sagc_put_u32(buf + 4, r->ambulance_id);
    sagc_put_u32(buf + 8, r->sequence_number);

    sagc_put_u32(buf + 12, (uint32_t)r->latitude);
    sagc_put_u32(buf + 16, (uint32_t)r->longitude);

    sagc_put_u16(buf + 20, r->speed_kmph);

    buf[22] = 0;
    buf[23] = 0;

    sagc_put_u64(buf + 24, r->timestamp_ms);

    memcpy(
        buf + SAGC_WIRE_AUTH_OFFSET,
        r->auth_tag,
        SAGC_HMAC_SIZE
    );
}


/* =====================================================
   26. UDP DECODING FUNCTION
   ===================================================== */

/* Converts the received 64-byte UDP packet
   into an AmbulanceRequest structure.

   Returns:
   0  = successful decoding
   -1 = invalid packet length or field

   IMPORTANT:
   This function does NOT verify HMAC, timestamp
   freshness or sequence number. P2 must do that
   separately before accepting the request. */

static inline int sagc_decode_request(
    const uint8_t *buf,
    uint32_t len,
    AmbulanceRequest *r)
{
    if (buf == 0 || r == 0)
        return -1;

    if (len != SAGC_WIRE_PACKET_SIZE)
        return -1;

    if (buf[0] != SAGC_PROTOCOL_VERSION)
        return -1;

    /* Check reserved bytes */
    if (buf[3] != 0 || buf[22] != 0 || buf[23] != 0)
        return -1;

    r->protocol_version = buf[0];
    r->triage_level = buf[1];
    r->flags = buf[2];

    r->ambulance_id = sagc_get_u32(buf + 4);
    r->sequence_number = sagc_get_u32(buf + 8);

    r->latitude = (int32_t)sagc_get_u32(buf + 12);
    r->longitude = (int32_t)sagc_get_u32(buf + 16);

    r->speed_kmph = sagc_get_u16(buf + 20);

    r->timestamp_ms = sagc_get_u64(buf + 24);

    memcpy(
        r->auth_tag,
        buf + SAGC_WIRE_AUTH_OFFSET,
        SAGC_HMAC_SIZE
    );

    /* Validate emergency priority */
    if (r->triage_level < 1 || r->triage_level > 5)
        return -1;

    /* Validate geographical coordinate ranges */
    if (r->latitude < -90000000 ||
        r->latitude > 90000000)
        return -1;

    if (r->longitude < -180000000 ||
        r->longitude > 180000000)
        return -1;

    return 0;
}


/* =====================================================
   27. CONSTANT-TIME AUTHENTICATION COMPARISON
   ===================================================== */

/* Compares two HMAC tags without stopping at the
   first different byte.

   Returns:
   1 = tags match
   0 = tags do not match */

static inline int sagc_ct_equal(
    const uint8_t *a,
    const uint8_t *b,
    uint32_t n)
{
    uint8_t diff = 0;
    uint32_t i;

    for (i = 0; i < n; i++)
    {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }

    return diff == 0;
}


/* =====================================================
   28. HMAC FUNCTION DECLARATION
   ===================================================== */

/* Calculates HMAC-SHA256.

   This function will be implemented in a separate
   source file, such as sagc_crypto.c.

   Both P1 and P2 use the same implementation.

   Returns:
   0 = successful calculation
   Non-zero = error */

int sagc_hmac_sha256(
    const uint8_t *key,
    uint32_t key_len,
    const uint8_t *msg,
    uint32_t msg_len,
    uint8_t out[SAGC_HMAC_SIZE]
);


/* =====================================================
   END OF SAGC COMMON HEADER
   ===================================================== */

#endif /* SHARED_CORRIDOR_H */
