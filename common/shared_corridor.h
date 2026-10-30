#ifndef SHARED_CORRIDOR_H
#define SHARED_CORRIDOR_H

/*
 * SMART AMBULANCE GREEN CORRIDOR (SAGC)
 * Shared interface contract - Version 2.0
 * Hardware: Raspberry Pi 4B | RTOS: QNX SDP 8.0
 *
 * Network model:
 *   P1 (ambulance simulator) -- UDP --> P2 (QNX)
 *   P2 -- QNX IPC --> P4; P2 -- heartbeat --> P3
 *   P3 -- QNX IPC fault --> P4
 *   P4 -- QNX IPC command --> P5; P5 -- feedback --> P4
 *   P4 -- dashboard bridge/UDP --> P6 (Windows laptop)
 *   P6 -- route decision/fault injection UDP --> QNX bridge/P1
 *
 * IMPORTANT:
 * - Do not transmit C structs directly as UDP bytes. Use the documented
 *   wire encoders or an explicitly agreed JSON serializer for dashboard data.
 * - P4 is the ONLY priority scheduler and route recommender.
 * - P5 executes authorised commands; it does not schedule ambulances.
 * - Four ambulances can be at one junction or distributed across J1..J4.
 * - Direction means the approach from which an ambulance enters its NEXT
 *   junction: NORTH, SOUTH, EAST or WEST.
 * - The route is a sequence of junction IDs (1..4), maximum four entries.
 * - Diversion is a recommendation. P4 waits for P6/operator confirmation
 *   before changing the active route.
 * - This is an academic simulation interface, not a certified road controller.
 */

#include <stdint.h>
#include <string.h>

#define SAGC_PROTOCOL_VERSION             2u
#define SAGC_MAX_JUNCTIONS                4u
#define SAGC_MAX_AMBULANCES               4u
#define SAGC_MAX_ROUTE_HOPS               4u
#define SAGC_HMAC_SIZE                    32u
#define SAGC_PSK_SIZE                     32u

#define SAGC_HEARTBEAT_INTERVAL_MS        500u
#define SAGC_WATCHDOG_TIMEOUT_MS          2000u
#define SAGC_PACKET_SEND_INTERVAL_MS      500u
#define SAGC_PACKET_STALE_MS              2000u
#define SAGC_P5_COMMAND_TIMEOUT_MS        2000u
#define SAGC_GEOFENCE_RADIUS_M             500u
#define SAGC_ETA_THRESHOLD_SEC             30u
#define SAGC_YELLOW_MS                     3000u
#define SAGC_ALL_RED_MS                    2000u
#define SAGC_PREPARE_LEAD_SEC              ((SAGC_YELLOW_MS + SAGC_ALL_RED_MS) / 1000u)
#define SAGC_PREPARE_ETA_SEC               (SAGC_ETA_THRESHOLD_SEC + SAGC_PREPARE_LEAD_SEC)

#define SAGC_UDP_PORT_AMBULANCE            5000u
#define SAGC_UDP_PORT_FAULT_INJECT         5001u
#define SAGC_UDP_PORT_DASHBOARD_STATUS     5002u
#define SAGC_UDP_PORT_ROUTE_DECISION       5003u

#define SAGC_NAME_P3_WATCHDOG              "sagc_p3"
#define SAGC_NAME_P4_CONTROLLER            "sagc_p4"
#define SAGC_NAME_P5_SIGNAL                "sagc_p5"
#define SAGC_NAME_P6_BRIDGE                "sagc_p6_bridge"

#define SAGC_FLAG_SESSION_END              0x01u
#define SAGC_FLAG_GPS_VALID                0x02u
#define SAGC_FLAG_ROUTE_VALID              0x04u

#define SAGC_REPLY_OK                      0u
#define SAGC_REPLY_REJECTED                1u

/* Message types for local QNX IPC and dashboard bridge messages. */
typedef enum {
    MSG_AMBULANCE_REQUEST = 1,
    MSG_EMERGENCY_REQUEST,
    MSG_HEARTBEAT,
    MSG_FAULT_ALERT,
    MSG_SIGNAL_COMMAND,
    MSG_SIGNAL_FEEDBACK,
    MSG_SYSTEM_STATUS,
    MSG_ROUTE_RECOMMENDATION,
    MSG_ROUTE_DECISION,
    MSG_AMBULANCE_PASSED,
    MSG_AMBULANCE_CANCEL
} SagcMessageType;

typedef enum {
    PROCESS_P1_AMBULANCE = 1,
    PROCESS_P2_INGESTION,
    PROCESS_P3_WATCHDOG,
    PROCESS_P4_CONTROLLER,
    PROCESS_P5_SIGNAL,
    PROCESS_P6_DASHBOARD
} SagcProcessID;

typedef enum {
    APPROACH_UNKNOWN = 0,
    APPROACH_NORTH = 1,
    APPROACH_SOUTH = 2,
    APPROACH_EAST = 3,
    APPROACH_WEST = 4
} ApproachDirection;

typedef enum {
    SIGNAL_RED = 0,
    SIGNAL_YELLOW,
    SIGNAL_GREEN,
    SIGNAL_FLASH_AMBER
} SignalState;

typedef enum {
    CORRIDOR_NORMAL = 0,
    CORRIDOR_PREPARING,
    CORRIDOR_ALL_RED,
    CORRIDOR_AMBULANCE_GREEN,
    CORRIDOR_CLEARING,
    CORRIDOR_FLASH_AMBER
} CorridorState;

typedef enum {
    FAULT_NONE = 0,
    FAULT_P2_TIMEOUT,
    FAULT_P4_TIMEOUT,
    FAULT_INVALID_PACKET,
    FAULT_AUTHENTICATION_FAILED,
    FAULT_REPLAY_DETECTED,
    FAULT_GPS_UNAVAILABLE,
    FAULT_NO_VALID_PACKET,
    FAULT_SIGNAL_OUTPUT_FAILED,
    FAULT_DASHBOARD_LINK_FAILED,
    FAULT_ROUTE_UNAVAILABLE
} SagcFaultCode;

#define SAGC_SEVERITY_INFO       1u
#define SAGC_SEVERITY_DEGRADE    2u
#define SAGC_SEVERITY_CRITICAL   3u

typedef enum {
    INJECT_NONE = 0,
    INJECT_GPS_LOSS,
    INJECT_BAD_MAC,
    INJECT_REPLAY,
    INJECT_PACKET_DELAY,
    INJECT_PACKET_LOSS,
    INJECT_CLEAR_ALL
} FaultInjectType;

typedef enum {
    AMBULANCE_IDLE = 0,
    AMBULANCE_APPROACHING,
    AMBULANCE_WAITING,
    AMBULANCE_SELECTED,
    AMBULANCE_CLEARED,
    AMBULANCE_PASSED,
    AMBULANCE_ROUTE_RECOMMENDED,
    AMBULANCE_WAITING_FOR_ROUTE_CONFIRMATION,
    AMBULANCE_COMPLETED,
    AMBULANCE_FAULT
} AmbulanceStatusCode;

typedef enum {
    ROUTE_REASON_BLOCKED = 1,
    ROUTE_REASON_HIGH_DELAY,
    ROUTE_REASON_LOWER_TRAVEL_TIME
} RouteRecommendationReason;

typedef enum {
    ROUTE_DECISION_PENDING = 0,
    ROUTE_DECISION_ACCEPTED = 1,
    ROUTE_DECISION_REJECTED = 2
} RouteDecisionCode;

/* P1 -> P2 logical request. Coordinates are signed microdegrees. */
typedef struct {
    uint8_t protocol_version;
    uint8_t triage_level;       /* 1 = highest, 5 = lowest */
    uint8_t flags;
    uint8_t approach_direction;
    uint32_t ambulance_id;      /* unique: 1..4 in the demo */
    uint32_t sequence_number;   /* increases for each ambulance update */
    uint8_t current_junction_id;/* 0 if between junctions, otherwise 1..4 */
    uint8_t next_junction_id;   /* target junction for this approach, 1..4 */
    uint8_t destination_junction_id; /* 1..4 */
    uint8_t route_count;        /* 0..SAGC_MAX_ROUTE_HOPS */
    uint8_t route[SAGC_MAX_ROUTE_HOPS]; /* ordered junction IDs */
    int32_t latitude;
    int32_t longitude;
    uint16_t speed_kmph;
    uint64_t sender_time_ms;    /* diagnostics only; do not compare clocks across hosts */
    uint8_t auth_tag[SAGC_HMAC_SIZE];
} AmbulanceRequest;

/* P2 -> P4 after packet, HMAC, sequence and field validation. */
typedef struct {
    uint32_t ambulance_id;
    uint32_t sequence_number;
    uint8_t triage_level;
    uint8_t flags;
    uint8_t approach_direction;
    uint8_t current_junction_id;
    uint8_t next_junction_id;
    uint8_t destination_junction_id;
    uint8_t route_count;
    uint8_t route[SAGC_MAX_ROUTE_HOPS];
    int32_t latitude;
    int32_t longitude;
    uint16_t speed_kmph;
    uint64_t received_time_ms;  /* receiver's local monotonic time */
    uint8_t authenticated;
    uint8_t gps_valid;
} EmergencyRequest;

typedef struct {
    uint32_t process_id;
    uint32_t sequence_number;
    uint64_t timestamp_ms;      /* sender-local monotonic time */
    uint8_t process_healthy;
    uint32_t rejected_packets;
} HeartbeatMessage;

typedef struct {
    uint32_t source_process_id;
    SagcFaultCode fault_code;
    uint64_t timestamp_ms;
    uint8_t severity;
    uint32_t detail;
} FaultMessage;

/* P4 -> P5. One command controls one junction and one safe phase. */
typedef struct {
    uint32_t junction_id;       /* 1..4 */
    uint32_t ambulance_id;      /* 0 for non-ambulance/all-red command */
    uint32_t movement_id;        /* stable movement/phase identifier from P4 config */
    SignalState north;
    SignalState south;
    SignalState east;
    SignalState west;
    CorridorState corridor_state;
    uint32_t command_sequence;
    uint64_t timestamp_ms;
} SignalCommand;

typedef struct {
    uint32_t junction_id;
    uint32_t ambulance_id;
    uint32_t movement_id;
    SignalState north;
    SignalState south;
    SignalState east;
    SignalState west;
    uint32_t command_sequence;
    uint8_t command_applied;
    uint32_t switch_latency_us;
    uint64_t timestamp_ms;
} SignalFeedback;

typedef struct {
    uint32_t junction_id;
    int32_t latitude;
    int32_t longitude;
    uint8_t is_active;
} JunctionInfo;

typedef struct {
    uint32_t junction_id;
    CorridorState state;
    uint32_t ambulance_count;
    uint8_t active;
} JunctionStatus;

typedef struct {
    uint32_t ambulance_id;
    uint8_t triage_level;
    uint8_t approach_direction;
    uint8_t current_junction_id;
    uint8_t next_junction_id;
    uint8_t destination_junction_id;
    uint8_t route_count;
    uint8_t route[SAGC_MAX_ROUTE_HOPS];
    uint32_t eta_seconds;
    uint32_t priority_score;
    AmbulanceStatusCode status;
    uint8_t diversion_pending;
} AmbulanceStatus;

/* P4 -> P6: status includes all four ambulances and all four junctions. */
typedef struct {
    uint32_t ambulance_count;
    AmbulanceStatus ambulances[SAGC_MAX_AMBULANCES];
    uint32_t junction_count;
    JunctionStatus junctions[SAGC_MAX_JUNCTIONS];
    uint8_t fault_active;
    SagcFaultCode current_fault;
    uint32_t rejected_packets;
    uint32_t last_switch_latency_us;
    uint64_t timestamp_ms;
} SystemStatus;

/* P4 -> P6: suggestion only; it does not change the active route. */
typedef struct {
    uint32_t ambulance_id;
    uint32_t recommendation_id;
    uint8_t reason;             /* RouteRecommendationReason */
    uint8_t route_count;
    uint8_t recommended_route[SAGC_MAX_ROUTE_HOPS];
    uint32_t estimated_travel_time_sec;
    uint32_t estimated_time_saved_sec;
    uint64_t timestamp_ms;
} RouteRecommendation;

/* P6/operator -> P4: explicit accept/reject for a recommendation. */
typedef struct {
    uint32_t ambulance_id;
    uint32_t recommendation_id;
    RouteDecisionCode decision;
    uint64_t timestamp_ms;
} RouteDecision;

typedef struct {
    uint32_t ambulance_id;
    uint32_t junction_id;
    uint64_t timestamp_ms;
} AmbulancePassedMessage;

typedef struct {
    uint32_t ambulance_id;
    uint32_t reason_code;
    uint64_t timestamp_ms;
} AmbulanceCancelMessage;

typedef struct {
    FaultInjectType inject_type;
    uint32_t duration_ms;
    uint32_t command_sequence;
    uint64_t timestamp_ms;
} FaultInjectCommand;

/* Local QNX IPC envelope. Use MsgSend/MsgReceive with this type. */
typedef struct {
    SagcMessageType message_type;
    uint32_t sender_process_id;
    union {
        EmergencyRequest emergency_request;
        HeartbeatMessage heartbeat;
        FaultMessage fault;
        SignalCommand signal_command;
        SignalFeedback signal_feedback;
        SystemStatus system_status;
        RouteRecommendation route_recommendation;
        RouteDecision route_decision;
        AmbulancePassedMessage ambulance_passed;
        AmbulanceCancelMessage ambulance_cancel;
    } data;
} SagcIpcMessage;

typedef struct { uint32_t status; } SagcIpcReply;

/* P1 -> P2 fixed UDP request packet, version 2, 72 bytes, big-endian:
 * 0 version, 1 triage, 2 flags, 3 approach,
 * 4..7 ambulance_id, 8..11 sequence,
 * 12 current_junction, 13 next_junction, 14 destination, 15 route_count,
 * 16..19 route[4], 20..23 latitude, 24..27 longitude,
 * 28..29 speed, 30..31 reserved, 32..39 sender_time_ms,
 * 40..71 HMAC-SHA256 over bytes 0..39.
 */
#define SAGC_WIRE_PACKET_SIZE       72u
#define SAGC_WIRE_AUTH_OFFSET      40u

static inline void sagc_put_u16(uint8_t *p, uint16_t v) {
    p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v;
}
static inline void sagc_put_u32(uint8_t *p, uint32_t v) {
    p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16);
    p[2]=(uint8_t)(v>>8);  p[3]=(uint8_t)v;
}
static inline void sagc_put_u64(uint8_t *p, uint64_t v) {
    sagc_put_u32(p, (uint32_t)(v >> 32)); sagc_put_u32(p+4, (uint32_t)v);
}
static inline uint16_t sagc_get_u16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | p[1]);
}
static inline uint32_t sagc_get_u32(const uint8_t *p) {
    return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];
}
static inline uint64_t sagc_get_u64(const uint8_t *p) {
    return ((uint64_t)sagc_get_u32(p)<<32) | sagc_get_u32(p+4);
}

static inline int sagc_validate_route(const uint8_t *route, uint8_t count) {
    uint8_t i;
    if (count > SAGC_MAX_ROUTE_HOPS) return 0;
    if (count > 0 && route == 0) return 0;
    for (i=0; i<count; ++i) if (route[i] < 1 || route[i] > SAGC_MAX_JUNCTIONS) return 0;
    return 1;
}

static inline void sagc_encode_request(const AmbulanceRequest *r, uint8_t buf[SAGC_WIRE_PACKET_SIZE]) {
    uint8_t i;
    memset(buf, 0, SAGC_WIRE_PACKET_SIZE);
    buf[0]=r->protocol_version; buf[1]=r->triage_level; buf[2]=r->flags; buf[3]=r->approach_direction;
    sagc_put_u32(buf+4,r->ambulance_id); sagc_put_u32(buf+8,r->sequence_number);
    buf[12]=r->current_junction_id; buf[13]=r->next_junction_id;
    buf[14]=r->destination_junction_id; buf[15]=r->route_count;
    for(i=0;i<SAGC_MAX_ROUTE_HOPS;i++) buf[16+i]=(i<r->route_count)?r->route[i]:0;
    sagc_put_u32(buf+20,(uint32_t)r->latitude); sagc_put_u32(buf+24,(uint32_t)r->longitude);
    sagc_put_u16(buf+28,r->speed_kmph); sagc_put_u64(buf+32,r->sender_time_ms);
    memcpy(buf+SAGC_WIRE_AUTH_OFFSET,r->auth_tag,SAGC_HMAC_SIZE);
}

/* Decode/field validation only. P2 MUST additionally verify HMAC and sequence.
 * Freshness must use P2's local receive time; sender monotonic clocks on
 * Windows and QNX do not share an epoch and must not be compared directly.
 */
static inline int sagc_decode_request(const uint8_t *buf, uint32_t len, AmbulanceRequest *r) {
    uint8_t i;
    if (!buf || !r || len != SAGC_WIRE_PACKET_SIZE) return -1;
    if (buf[0] != SAGC_PROTOCOL_VERSION || buf[30] != 0 || buf[31] != 0) return -1;
    if (buf[1] < 1 || buf[1] > 5) return -1;
    if (buf[3] < APPROACH_NORTH || buf[3] > APPROACH_WEST) return -1;
    if (buf[12] > SAGC_MAX_JUNCTIONS || buf[13] < 1 || buf[13] > SAGC_MAX_JUNCTIONS ||
        buf[14] < 1 || buf[14] > SAGC_MAX_JUNCTIONS || buf[15] > SAGC_MAX_ROUTE_HOPS) return -1;
    r->protocol_version=buf[0]; r->triage_level=buf[1]; r->flags=buf[2]; r->approach_direction=buf[3];
    r->ambulance_id=sagc_get_u32(buf+4); r->sequence_number=sagc_get_u32(buf+8);
    r->current_junction_id=buf[12]; r->next_junction_id=buf[13];
    r->destination_junction_id=buf[14]; r->route_count=buf[15];
    for(i=0;i<SAGC_MAX_ROUTE_HOPS;i++) r->route[i]=buf[16+i];
    if (!sagc_validate_route(r->route,r->route_count)) return -1;
    for(i=r->route_count;i<SAGC_MAX_ROUTE_HOPS;i++) if(r->route[i]!=0) return -1;
    r->latitude=(int32_t)sagc_get_u32(buf+20); r->longitude=(int32_t)sagc_get_u32(buf+24);
    if(r->latitude < -90000000 || r->latitude > 90000000 || r->longitude < -180000000 || r->longitude > 180000000) return -1;
    r->speed_kmph=sagc_get_u16(buf+28); r->sender_time_ms=sagc_get_u64(buf+32);
    memcpy(r->auth_tag,buf+SAGC_WIRE_AUTH_OFFSET,SAGC_HMAC_SIZE);
    if(r->ambulance_id==0 || r->sequence_number==0) return -1;
    return 0;
}

static inline int sagc_ct_equal(const uint8_t *a, const uint8_t *b, uint32_t n) {
    uint8_t diff=0; uint32_t i;
    if(!a || !b) return 0;
    for(i=0;i<n;i++) diff |= (uint8_t)(a[i]^b[i]);
    return diff==0;
}

int sagc_hmac_sha256(const uint8_t *key, uint32_t key_len,
                     const uint8_t *msg, uint32_t msg_len,
                     uint8_t out[SAGC_HMAC_SIZE]);

#endif /* SHARED_CORRIDOR_H */
