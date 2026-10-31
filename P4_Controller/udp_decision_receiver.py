
import socket
import json
import threading


P4_HOST = "127.0.0.1"
P4_PORT = 6003


class UDPDecisionReceiver:

    def __init__(self, route_recommender, on_decision=None):
        self.route_recommender = route_recommender
        self.on_decision = on_decision
        self.running = False
        self.udp_socket = None

    def start(self):

        if self.running:
            return

        self.running = True

        receiver_thread = threading.Thread(
            target=self.receive_decisions,
            daemon=True
        )

        receiver_thread.start()

        print(
            f"[P4] Waiting for dashboard decisions "
            f"on {P4_HOST}:{P4_PORT}"
        )

    def receive_decisions(self):

        try:
            self.udp_socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )

            self.udp_socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1
            )

            self.udp_socket.bind((P4_HOST, P4_PORT))

            while self.running:

                data, address = self.udp_socket.recvfrom(4096)

                try:
                    decision = json.loads(data.decode("utf-8"))

                    ambulance_id = decision.get("ambulance_id")
                    recommendation_id = decision.get("recommendation_id")
                    action = decision.get("action")

                    if not ambulance_id or recommendation_id is None:
                        print("[P4] Invalid decision message")
                        continue

                    if action not in ("APPROVE", "REJECT"):
                        print("[P4] Unknown decision action")
                        continue

                    pending = (
                        self.route_recommender.pending_recommendations.get(
                            ambulance_id
                        )
                    )

                    if pending is None:
                        print(
                            f"[P4] No pending recommendation for "
                            f"{ambulance_id}"
                        )
                        continue

                    if pending["recommendation_id"] != recommendation_id:
                        print("[P4] Recommendation ID mismatch")
                        continue

                    approved = action == "APPROVE"

                    success = self.route_recommender.decide_route(
                        ambulance_id,
                        approved
                    )

                    if success:
                        print(
                            f"[P4] Dashboard decision processed: "
                            f"{action} for {ambulance_id}"
                        )

                        if self.on_decision:
                            self.on_decision()

                except (json.JSONDecodeError, UnicodeDecodeError):
                    print("[P4] Invalid JSON received")

                except Exception as error:
                    print(f"[P4] Decision processing error: {error}")

        except OSError as error:
            if self.running:
                print(f"[P4] UDP receiver error: {error}")

    def close(self):

        self.running = False

        if self.udp_socket:
            self.udp_socket.close()
