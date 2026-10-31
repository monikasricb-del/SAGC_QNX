
from flask import Flask, render_template, jsonify, request
from udp_receiver import start_receiver, get_latest_status
import socket
import json

app = Flask(__name__)

# P4 decision receiver
P4_HOST = "127.0.0.1"
P4_PORT = 6003

# Start P4-to-P6 status receiver
start_receiver()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/status")
def get_status():
    return jsonify(get_latest_status())


@app.route("/api/route-decision", methods=["POST"])
def route_decision():

    try:
        decision = request.get_json()

        if not decision:
            return jsonify({
                "success": False,
                "message": "Missing decision data"
            }), 400

        ambulance_id = decision.get("ambulance_id")
        recommendation_id = decision.get("recommendation_id")
        action = decision.get("action")

        if not ambulance_id or recommendation_id is None:
            return jsonify({
                "success": False,
                "message": "Missing ambulance or recommendation ID"
            }), 400

        if action not in ("APPROVE", "REJECT"):
            return jsonify({
                "success": False,
                "message": "Invalid action"
            }), 400

        message = json.dumps({
            "ambulance_id": ambulance_id,
            "recommendation_id": recommendation_id,
            "action": action
        }).encode("utf-8")

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            udp_socket.sendto(message, (P4_HOST, P4_PORT))

        print(
            f"[P6] Sent {action} decision for "
            f"{ambulance_id} to P4"
        )

        return jsonify({
            "success": True,
            "message": f"{action} decision sent to P4"
        })

    except Exception as error:
        print(f"[P6] Route decision error: {error}")

        return jsonify({
            "success": False,
            "message": "Unable to send decision"
        }), 500


if __name__ == "__main__":
    print("Starting SAGC P6 Dashboard...")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )
