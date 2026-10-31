
import time


# Fault codes from shared_corridor.h
FAULT_P2_TIMEOUT = 1
FAULT_P4_TIMEOUT = 2
FAULT_INVALID_PACKET = 3
FAULT_AUTHENTICATION_FAILED = 4
FAULT_REPLAY_DETECTED = 5
FAULT_GPS_UNAVAILABLE = 6
FAULT_NO_VALID_PACKET = 7
FAULT_SIGNAL_OUTPUT_FAILED = 8
FAULT_DASHBOARD_LINK_FAILED = 9
FAULT_ROUTE_UNAVAILABLE = 10

PROCESS_IDS = {
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4,
    "P5": 5,
    "P6": 6
}


class FaultMonitor:

    HEARTBEAT_TIMEOUT = 2.0

    def __init__(self):

        self.heartbeats = {}
        self.process_health = {}
        self.junction_faults = {}

        self.monitored_processes = ["P2", "P3", "P5"]

        for process in self.monitored_processes:
            self.process_health[process] = "UNKNOWN"

    def receive_heartbeat(self, process_id):

        if process_id not in self.monitored_processes:
            print(f"[ERROR] Unknown process: {process_id}")
            return False

        self.heartbeats[process_id] = time.monotonic()

        previous_health = self.process_health[process_id]
        self.process_health[process_id] = "HEALTHY"

        if previous_health == "FAILED":
            print(f"[RECOVERED] {process_id} is HEALTHY")
        else:
            print(f"[HEARTBEAT] {process_id} is HEALTHY")

        return True

    def check_heartbeats(self):

        current_time = time.monotonic()

        for process in self.monitored_processes:

            last_heartbeat = self.heartbeats.get(process)

            if last_heartbeat is None:
                self.process_health[process] = "UNKNOWN"
                continue

            elapsed = current_time - last_heartbeat

            if elapsed > self.HEARTBEAT_TIMEOUT:

                if self.process_health[process] != "FAILED":
                    print(
                        f"[FAULT DETECTED] {process} heartbeat "
                        f"timeout ({elapsed:.2f}s)"
                    )

                self.process_health[process] = "FAILED"

        return self.process_health.copy()

    def report_junction_fault(
        self,
        junction_id,
        fault_reason,
        fault_code=FAULT_SIGNAL_OUTPUT_FAILED
    ):

        if junction_id not in range(1, 5):
            print("[ERROR] Invalid junction ID")
            return False

        self.junction_faults[junction_id] = {
            "status": "FAULT",
            "fault_code": fault_code,
            "reason": fault_reason,
            "detected_at_ms": int(time.monotonic() * 1000)
        }

        print(
            f"[JUNCTION FAULT] J{junction_id}: {fault_reason}"
        )

        return True

    def clear_junction_fault(self, junction_id):

        if junction_id not in self.junction_faults:
            print(f"[INFO] No recorded fault at J{junction_id}")
            return False

        del self.junction_faults[junction_id]

        print(f"[FAULT CLEARED] J{junction_id}")

        return True

    def is_junction_available(self, junction_id):

        if junction_id not in range(1, 5):
            return False

        return junction_id not in self.junction_faults

    def is_process_healthy(self, process_id):

        return self.process_health.get(process_id) == "HEALTHY"

    def get_system_health(self):

        return {
            "process_health": self.process_health.copy(),
            "junction_faults": self.junction_faults.copy()
        }


if __name__ == "__main__":

    monitor = FaultMonitor()

    print("===== P4 FAULT MONITOR TEST =====")

    print("\nTEST 1 - HEARTBEAT RECEPTION")

    monitor.receive_heartbeat("P2")
    monitor.receive_heartbeat("P3")
    monitor.receive_heartbeat("P5")

    print(monitor.check_heartbeats())

    print("\nTEST 2 - HEARTBEAT TIMEOUT")

    monitor.heartbeats["P2"] = time.monotonic() - 3.0

    print(monitor.check_heartbeats())

    print("\nTEST 3 - PROCESS RECOVERY")

    monitor.receive_heartbeat("P2")

    print(monitor.check_heartbeats())

    print("\nTEST 4 - JUNCTION FAULT")

    monitor.report_junction_fault(
        2,
        "Traffic signal controller not responding"
    )

    print("Is J2 available?", monitor.is_junction_available(2))

    print("\nTEST 5 - FAULT CLEARANCE")

    monitor.clear_junction_fault(2)

    print("Is J2 available?", monitor.is_junction_available(2))

    print("\nFINAL SYSTEM HEALTH")

    print(monitor.get_system_health())
