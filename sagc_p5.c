/*
 * Smart Ambulance Green Corridor (SAGC)
 * P5 - Traffic Signal Output Controller
 *
 * Responsibilities:
 * 1. Receive signal commands through QNX message passing.
 * 2. Validate junction IDs and signal states.
 * 3. Reject conflicting signal combinations.
 * 4. Reject duplicate or out-of-order command sequences.
 * 5. Update the stored signal state.
 * 6. Reply to the sending process.
 *
 * NOTE:
 * This is a development-stage implementation.
 * The conflict-validation rule is preliminary and must be
 * replaced with an approved movement-conflict matrix before
 * hardware or real traffic-signal use.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <errno.h>
#include <string.h>
#include <time.h>

#include <sys/neutrino.h>
#include <sys/dispatch.h>

#include "../common/shared_corridor.h"
#define MAX_JUNCTIONS 4
#define DIRECTIONS 4

/*
 * Direction indexes:
 * 0 = North
 * 1 = South
 * 2 = East
 * 3 = West
 */

static SignalState junction_signals[MAX_JUNCTIONS][DIRECTIONS];

/* Track the latest accepted command sequence for each junction. */
static uint32_t last_command_sequence[MAX_JUNCTIONS];
static int sequence_initialized[MAX_JUNCTIONS];

/* Return the current time in milliseconds. */
static uint64_t current_time_ms(void)
{
    struct timespec ts;

    if (clock_gettime(CLOCK_REALTIME, &ts) == -1) {
        return 0;
    }

    return ((uint64_t)ts.tv_sec * 1000ULL) +
           ((uint64_t)ts.tv_nsec / 1000000ULL);
}

/* Validate an individual signal state. */
static int valid_signal(SignalState signal)
{
    return signal >= SIGNAL_RED &&
           signal <= SIGNAL_FLASH_AMBER;
}

/*
 * Preliminary conflict check:
 * Reject simultaneous North/South and East/West green signals.
 *
 * IMPORTANT:
 * This is only a basic prototype check, not a complete
 * real-world traffic movement-conflict model.
 */
static int valid_signal_combination(const SignalCommand *cmd)
{
    int ns_green;
    int ew_green;

    ns_green = (cmd->north == SIGNAL_GREEN) ||
               (cmd->south == SIGNAL_GREEN);

    ew_green = (cmd->east == SIGNAL_GREEN) ||
               (cmd->west == SIGNAL_GREEN);

    if (ns_green && ew_green) {
        return 0;
    }

    return 1;
}

/* Initialize all junctions to RED and clear sequence tracking. */
static void initialize_signals(void)
{
    unsigned int j;
    unsigned int d;

    for (j = 0; j < MAX_JUNCTIONS; j++) {
        for (d = 0; d < DIRECTIONS; d++) {
            junction_signals[j][d] = SIGNAL_RED;
        }

        last_command_sequence[j] = 0;
        sequence_initialized[j] = 0;
    }
}

/* Store the accepted signal command for a junction. */
static void apply_signal_command(const SignalCommand *cmd)
{
    unsigned int index = cmd->junction_id - 1;

    junction_signals[index][0] = cmd->north;
    junction_signals[index][1] = cmd->south;
    junction_signals[index][2] = cmd->east;
    junction_signals[index][3] = cmd->west;

    /* Remember the accepted sequence number. */
    last_command_sequence[index] = cmd->command_sequence;
    sequence_initialized[index] = 1;
}

/* Print the accepted signal states for debugging. */
static void print_signal_command(const SignalCommand *cmd)
{
    printf(
        "P5: J%u | Ambulance: %u | Movement: %u | "
        "N:%d S:%d E:%d W:%d | Sequence:%u | Time:%llu ms\n",
        (unsigned int)cmd->junction_id,
        (unsigned int)cmd->ambulance_id,
        (unsigned int)cmd->movement_id,
        (int)cmd->north,
        (int)cmd->south,
        (int)cmd->east,
        (int)cmd->west,
        (unsigned int)cmd->command_sequence,
        (unsigned long long)current_time_ms()
    );
}

int main(void)
{
    int chid;
    int rcvid;
    int receive_error;

    SagcIpcMessage message;
    SagcIpcReply reply;

    printf("============================================\n");
    printf(" SAGC P5 - Traffic Signal Output Controller\n");
    printf("============================================\n");

    initialize_signals();

    /*
     * Create a QNX message-passing channel.
     * Other processes must have an agreed method to connect
     * to this channel before they can send commands.
     */
    chid = ChannelCreate(0);

    if (chid == -1) {
        perror("P5: ChannelCreate failed");
        return EXIT_FAILURE;
    }

    printf("P5: QNX channel created successfully. Channel ID: %d\n",
           chid);

    printf("P5: All four junctions initialized to RED.\n");
    printf("P5: Waiting for signal commands...\n");

    while (1) {
        memset(&message, 0, sizeof(message));
        memset(&reply, 0, sizeof(reply));

        rcvid = MsgReceive(
            chid,
            &message,
            sizeof(message),
            NULL
        );

        if (rcvid == -1) {
            receive_error = errno;

            if (receive_error == EINTR) {
                continue;
            }

            fprintf(stderr,
                    "P5: MsgReceive failed: %s\n",
                    strerror(receive_error));

            continue;
        }

        /* Accept only signal-command messages. */
        if (message.message_type != MSG_SIGNAL_COMMAND) {
            fprintf(stderr,
                    "P5: Rejected unsupported message type %d\n",
                    (int)message.message_type);

            reply.status = (uint32_t)EINVAL;

            if (MsgReply(rcvid, EOK,
                         &reply, sizeof(reply)) == -1) {
                perror("P5: MsgReply failed");
            }

            continue;
        }

        {
            SignalCommand *cmd = &message.data.signal_command;
            unsigned int index;

            /* Validate the junction ID before indexing arrays. */
            if (cmd->junction_id < 1 ||
                cmd->junction_id > MAX_JUNCTIONS) {

                fprintf(stderr,
                        "P5: Rejected invalid junction ID: %u\n",
                        (unsigned int)cmd->junction_id);

                reply.status = (uint32_t)EINVAL;

                if (MsgReply(rcvid, EOK,
                             &reply, sizeof(reply)) == -1) {
                    perror("P5: MsgReply failed");
                }

                continue;
            }

            /* Validate each individual signal state. */
            if (!valid_signal(cmd->north) ||
                !valid_signal(cmd->south) ||
                !valid_signal(cmd->east) ||
                !valid_signal(cmd->west)) {

                fprintf(stderr,
                        "P5: Rejected invalid signal state "
                        "at junction J%u\n",
                        (unsigned int)cmd->junction_id);

                reply.status = (uint32_t)EINVAL;

                if (MsgReply(rcvid, EOK,
                             &reply, sizeof(reply)) == -1) {
                    perror("P5: MsgReply failed");
                }

                continue;
            }

            /* Reject preliminary conflicting green combinations. */
            if (!valid_signal_combination(cmd)) {
                fprintf(stderr,
                        "P5: Rejected conflicting signal "
                        "combination at junction J%u\n",
                        (unsigned int)cmd->junction_id);

                reply.status = (uint32_t)EINVAL;

                if (MsgReply(rcvid, EOK,
                             &reply, sizeof(reply)) == -1) {
                    perror("P5: MsgReply failed");
                }

                continue;
            }

            index = cmd->junction_id - 1;

            /*
             * Reject duplicate or out-of-order commands.
             * This assumes P4 sends strictly increasing sequence
             * numbers for each junction during this P5 run.
             */
            if (sequence_initialized[index] &&
                cmd->command_sequence <=
                    last_command_sequence[index]) {

                fprintf(stderr,
                        "P5: Rejected duplicate/out-of-order "
                        "sequence %u at junction J%u; "
                        "last accepted sequence was %u\n",
                        (unsigned int)cmd->command_sequence,
                        (unsigned int)cmd->junction_id,
                        (unsigned int)
                            last_command_sequence[index]);

                reply.status = (uint32_t)EINVAL;

                if (MsgReply(rcvid, EOK,
                             &reply, sizeof(reply)) == -1) {
                    perror("P5: MsgReply failed");
                }

                continue;
            }

            /* Apply only a validated, new command. */
            apply_signal_command(cmd);

            print_signal_command(cmd);

            /* Status 0 indicates acceptance in this prototype. */
            reply.status = 0;

            if (MsgReply(rcvid, EOK,
                         &reply, sizeof(reply)) == -1) {
                perror("P5: MsgReply failed");
            }
        }
    }

    /* Normally unreachable in this loop. */
    ChannelDestroy(chid);

    return EXIT_SUCCESS;
}
