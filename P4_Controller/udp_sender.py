
import socket
import json


P6_HOST = "127.0.0.1"
P6_PORT = 6002


class UDPStatusSender:

    def __init__(self, host=P6_HOST, port=P6_PORT):
        self.host = host
        self.port = port
        self.udp_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

    def send_status(self, status):

        try:
            message = json.dumps(status).encode("utf-8")

            self.udp_socket.sendto(
                message,
                (self.host, self.port)
            )

            print(
                f"[P4] Status sent to P6 at "
                f"{self.host}:{self.port}"
            )

            return True

        except (TypeError, ValueError, OSError) as error:
            print(f"[P4] UDP sending failed: {error}")
            return False

    def close(self):
        self.udp_socket.close()
