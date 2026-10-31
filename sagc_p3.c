/*
 * Smart Ambulance Green Corridor (SAGC)
 * P3 - Watchdog / Fault Monitor
 * QNX SDP 8.0
 *
 * Responsibilities:
 * 1. Monitor P2 heartbeats.
 * 2. Detect missing first heartbeat.
 * 3. Detect heartbeat timeouts.
 * 4. Reject duplicate/out-of-order heartbeat sequences.
 * 5. Reconnect to P4 when its endpoint becomes available.
 * 6. Report detected P2 faults to P4.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <time.h>

#include <sys/neutrino.h>
#include <sys/dispatch.h>

#include "../common/shared_corridor.h"

#define P2_PROCESS_ID ((uint32_t)PROCESS_P2_INGESTION)

#define P3_RECEIVE_TIMEOUT_NS 100000000LL
#define P4_RETRY_INTERVAL_MS  1000ULL

static uint64_t monotonic_time_ms(void)
{
    struct timespec ts;

    if (clock_gettime(CLOCK_MONOTONIC, &ts) == -1) {
        return 0;
    }

    return ((uint64_t)ts.tv_sec * 1000ULL) +
           ((uint64_t)ts.tv_nsec / 1000000ULL);
}

/*
 * Send a fault to P4.
 *
 * Returns:
 *   0  = fault acknowledged by P4
 *  -1  = fault could not be delivered
 */
static int report_fault(
    int p4_coid,
    SagcFaultCode fault_code,
    uint32_t detail)
{
    SagcIpcMessage message;
    SagcIpcReply reply;

    if (p4_coid == -1) {
        return -1;
    }

    memset(&message, 0, sizeof(message));
    memset(&reply, 0, sizeof(reply));

    message.message_type = MSG_FAULT_ALERT;
    message.sender_process_id = PROCESS_P3_WATCHDOG;

    message.data.fault.source_process_id = P2_PROCESS_ID;
    message.data.fault.fault_code = fault_code;
    message.data.fault.timestamp_ms = monotonic_time_ms();
    message.data.fault.severity = SAGC_SEVERITY_CRITICAL;
    message.data.fault.detail = detail;

    if (MsgSend(
            p4_coid,
            &message,
            sizeof(message),
            &reply,
            sizeof(reply)) == -1) {

        fprintf(stderr,
                "P3: Fault delivery to P4 failed: %s\n",
                strerror(errno));

        return -1;
    }

    if (reply.status != SAGC_REPLY_OK) {
        fprintf(stderr,
                "P3: P4 did not acknowledge the fault.\n");
        return -1;
    }

    printf("P3: P4 acknowledged fault code %d.\n",
           (int)fault_code);

    return 0;
}

int main(void)
{
    name_attach_t *attach;
    int p4_coid = -1;
    int rcvid;

    SagcIpcMessage message;
    SagcIpcReply reply;

    uint64_t startup_time_ms;
    uint64_t last_heartbeat_ms = 0;
    uint64_t last_p4_retry_ms = 0;

    uint32_t last_sequence = 0;

    int heartbeat_seen = 0;
    int sequence_seen = 0;
    int timeout_reported = 0;

    int pending_fault = 0;
    SagcFaultCode pending_fault_code = FAULT_NONE;
    uint32_t pending_fault_detail = 0;

    printf("=====================================\n");
    printf(" SAGC P3 - Watchdog / Fault Monitor\n");
    printf("=====================================\n");

    startup_time_ms = monotonic_time_ms();

    /*
     * Register P3's named QNX message endpoint.
     * P2 must discover this endpoint and send heartbeats to it.
     */
    attach = name_attach(NULL, SAGC_NAME_P3_WATCHDOG, 0);

    if (attach == NULL) {
        perror("P3: name_attach failed");
        return EXIT_FAILURE;
    }

    printf("P3: Registered endpoint '%s'.\n",
           SAGC_NAME_P3_WATCHDOG);

    printf("P3: Waiting for P2 heartbeats.\n");
    printf("P3: Watchdog timeout = %u ms.\n",
           (unsigned int)SAGC_WATCHDOG_TIMEOUT_MS);

    while (1) {
        uint64_t now_ms;
        uint64_t reference_time_ms;
        uint64_t elapsed_ms;
        int receive_result;

        /*
         * Retry the P4 connection periodically if P4 was not
         * available when P3 started.
         */
        now_ms = monotonic_time_ms();

        if (p4_coid == -1 &&
            (now_ms - last_p4_retry_ms) >= P4_RETRY_INTERVAL_MS) {

            last_p4_retry_ms = now_ms;

            p4_coid = name_open(SAGC_NAME_P4_CONTROLLER, 0);

            if (p4_coid != -1) {
                printf("P3: Connected to P4 endpoint '%s'.\n",
                       SAGC_NAME_P4_CONTROLLER);
            }
        }

        /*
         * If a fault could not be delivered earlier, retain it
         * and retry after a P4 connection becomes available.
         */
        if (pending_fault && p4_coid != -1) {
            if (report_fault(
                    p4_coid,
                    pending_fault_code,
                    pending_fault_detail) == 0) {

                pending_fault = 0;
            } else {
                name_close(p4_coid);
                p4_coid = -1;
                last_p4_retry_ms = monotonic_time_ms();
            }
        }

        /*
         * Receive timeout lets P3 continue checking heartbeat
         * freshness even when no messages arrive.
         */
        {
            const uint64_t receive_timeout_ns =
                (uint64_t)P3_RECEIVE_TIMEOUT_NS;

            TimerTimeout(
                CLOCK_MONOTONIC,
                _NTO_TIMEOUT_RECEIVE,
                NULL,
                &receive_timeout_ns,
                NULL
            );
        }

        memset(&message, 0, sizeof(message));

        rcvid = MsgReceive(
            attach->chid,
            &message,
            sizeof(message),
            NULL
        );

        receive_result = rcvid;

        if (receive_result == -1) {
            if (errno != ETIMEDOUT && errno != EINTR) {
                fprintf(stderr,
                        "P3: MsgReceive failed: %s\n",
                        strerror(errno));
            }
        } else {
            memset(&reply, 0, sizeof(reply));

            if (message.message_type != MSG_HEARTBEAT) {
                fprintf(stderr,
                        "P3: Rejected unsupported message type %d.\n",
                        (int)message.message_type);

                reply.status = SAGC_REPLY_REJECTED;

                if (MsgReply(
                        rcvid, EOK,
                        &reply, sizeof(reply)) == -1) {
                    perror("P3: MsgReply failed");
                }
            } else {
                HeartbeatMessage *hb = &message.data.heartbeat;

                if (message.sender_process_id != P2_PROCESS_ID ||
                    hb->process_id != P2_PROCESS_ID) {

                    fprintf(stderr,
                            "P3: Rejected heartbeat from "
                            "unexpected process ID.\n");

                    reply.status = SAGC_REPLY_REJECTED;

                    if (MsgReply(
                            rcvid, EOK,
                            &reply, sizeof(reply)) == -1) {
                        perror("P3: MsgReply failed");
                    }
                } else if (sequence_seen &&
                           hb->sequence_number <= last_sequence) {

                    fprintf(stderr,
                            "P3: Rejected duplicate/out-of-order "
                            "heartbeat sequence %u.\n",
                            (unsigned int)hb->sequence_number);

                    reply.status = SAGC_REPLY_REJECTED;

                    if (MsgReply(
                            rcvid, EOK,
                            &reply, sizeof(reply)) == -1) {
                        perror("P3: MsgReply failed");
                    }
                } else {
                    last_sequence = hb->sequence_number;
                    sequence_seen = 1;

                    now_ms = monotonic_time_ms();
                    last_heartbeat_ms = now_ms;
                    heartbeat_seen = 1;
                    timeout_reported = 0;

                    if (hb->process_healthy) {
                        printf("P3: Healthy P2 heartbeat received. "
                               "Sequence=%u\n",
                               (unsigned int)hb->sequence_number);

                        reply.status = SAGC_REPLY_OK;
                    } else {
                        fprintf(stderr,
                                "P3: P2 reported an unhealthy state.\n");

                        pending_fault = 1;
                        pending_fault_code = FAULT_P2_TIMEOUT;
                        pending_fault_detail = hb->sequence_number;

                        reply.status = SAGC_REPLY_OK;
                    }

                    if (MsgReply(
                            rcvid, EOK,
                            &reply, sizeof(reply)) == -1) {
                        perror("P3: MsgReply failed");
                    }
                }
            }
        }

        /*
         * Detect missing first heartbeat or a later heartbeat
         * timeout. The timer uses P3's local monotonic clock.
         */
        now_ms = monotonic_time_ms();

        if (heartbeat_seen) {
            reference_time_ms = last_heartbeat_ms;
        } else {
            reference_time_ms = startup_time_ms;
        }

        if (now_ms >= reference_time_ms) {
            elapsed_ms = now_ms - reference_time_ms;

            if (elapsed_ms >= SAGC_WATCHDOG_TIMEOUT_MS &&
                !timeout_reported) {

                if (heartbeat_seen) {
                    fprintf(stderr,
                            "P3: ALERT - P2 heartbeat timed out "
                            "after %llu ms.\n",
                            (unsigned long long)elapsed_ms);
                } else {
                    fprintf(stderr,
                            "P3: ALERT - No first P2 heartbeat "
                            "received within %u ms.\n",
                            (unsigned int)SAGC_WATCHDOG_TIMEOUT_MS);
                }

                pending_fault = 1;
                pending_fault_code = FAULT_P2_TIMEOUT;
                pending_fault_detail = (uint32_t)elapsed_ms;

                timeout_reported = 1;
            }
        }
    }

    /* The loop normally runs indefinitely. */
    if (p4_coid != -1) {
        name_close(p4_coid);
    }

    name_detach(attach, 0);

    return EXIT_SUCCESS;
}
