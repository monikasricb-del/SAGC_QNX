
import socket
import json
import threading

UDP_HOST = "127.0.0.1"
UDP_PORT = 6002

latest_status = {}


def receive_p4_data():
    global latest_status

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((UDP_HOST, UDP_PORT))

    print(f"[P6] Waiting for P4 data on {UDP_HOST}:{UDP_PORT}")

    while True:
        try:
            data, address = udp_socket.recvfrom(65535)

            status = json.loads(data.decode("utf-8"))

            latest_status = status

            print(f"[P6] Received status from {address}")
            print(json.dumps(status, indent=4))

        except json.JSONDecodeError:
            print("[P6] Invalid JSON received")

        except Exception as error:
            print(f"[P6] Receiver error: {error}")


def start_receiver():
    receiver_thread = threading.Thread(
        target=receive_p4_data,
        daemon=True
    )

    receiver_thread.start()


def get_latest_status():
    return latest_status.copy()
