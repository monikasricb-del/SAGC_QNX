
from dataclasses import dataclass, asdict, is_dataclass
import time


@dataclass
class AmbulanceStatus:
    ambulance_id: int
    triage_level: int
    approach_direction: int
    current_junction_id: int
    next_junction_id: int
    destination_junction_id: int
    route_count: int
    route: list
    eta_seconds: float
    priority_score: float
    status: int
    diversion_pending: bool


@dataclass
class JunctionStatus:
    junction_id: int
    state: int
    ambulance_count: int
    active: bool


@dataclass
class SystemStatus:
    ambulance_count: int
    ambulances: list
    junction_count: int
    junctions: list
    fault_active: bool
    current_fault: int
    rejected_packets: int
    last_switch_latency_us: int
    timestamp_ms: int


class SystemStatusManager:

    def __init__(self):
        self.latest_status = {}
        self.last_switch_latency_us = 0
        self.rejected_packets = 0
        self.current_fault = 0

    def convert_to_dict(self, item):

        if is_dataclass(item):
            return asdict(item)

        if isinstance(item, dict):
            return item.copy()

        return {}

    def ambulance_id_to_number(self, ambulance_id):

        if isinstance(ambulance_id, int):
            return ambulance_id

        return int(ambulance_id.replace("AMB", ""))

    def approach_to_number(self, approach):

        mapping = {
            "UNKNOWN": 0,
            "NORTH": 1,
            "SOUTH": 2,
            "EAST": 3,
            "WEST": 4
        }

        return mapping.get(approach.upper(), 0)

    def corridor_state_to_number(self, state):

        mapping = {
            "NORMAL": 0,
            "PREPARING": 1,
            "ALL_RED": 2,
            "AMBULANCE_GREEN": 3,
            "CLEARING": 4,
            "FLASH_AMBER": 5
        }

        return mapping.get(state, 0)

    def generate_status(
        self,
        ambulances=None,
        junction_results=None,
        corridor_states=None,
        active_passages=None,
        fault_health=None,
        route_recommendations=None
    ):

        ambulances = ambulances or []
        junction_results = junction_results or {}
        corridor_states = corridor_states or {}
        active_passages = active_passages or {}
        fault_health = fault_health or {}
        route_recommendations = route_recommendations or {}

        ambulance_status = []

        for ambulance in ambulances:

            data = self.convert_to_dict(ambulance)

            ambulance_id = data.get("ambulance_id", "AMB00")
            junction_id = data.get("junction_id", 0)
            triage = data.get("triage_level", 0)
            eta = data.get("eta_seconds", 0)
            waiting = data.get("waiting_seconds", 0)
            approach = data.get("approach", "UNKNOWN")

            result = junction_results.get(junction_id, {})
            selected = result.get("selected", [])

            is_selected = any(
                item.ambulance_id == ambulance_id
                for item in selected
            )

            passage = active_passages.get(junction_id)

            if is_selected and passage:
                status_code = 3
                status_text = "SELECTED"
            elif is_selected:
                status_code = 2
                status_text = "SELECTED"
            else:
                status_code = 3
                status_text = "WAITING"

            recommendation = route_recommendations.get(
                ambulance_id
            )

            diversion_pending = recommendation is not None

            # The existing simulation does not yet calculate
            # a numeric priority score separately.
            priority_score = 0

            ambulance_status.append(
                AmbulanceStatus(
                    ambulance_id=self.ambulance_id_to_number(
                        ambulance_id
                    ),
                    triage_level=triage,
                    approach_direction=self.approach_to_number(
                        approach
                    ),
                    current_junction_id=junction_id,
                    next_junction_id=junction_id,
                    destination_junction_id=0,
                    route_count=0,
                    route=[],
                    eta_seconds=eta,
                    priority_score=priority_score,
                    status=status_code,
                    diversion_pending=diversion_pending
                )
            )

        junction_status = []

        for junction_id in range(1, 5):

            result = junction_results.get(
                junction_id,
                {"selected": [], "waiting": []}
            )

            selected = result.get("selected", [])
            waiting = result.get("waiting", [])

            state_name = corridor_states.get(
                junction_id, "NORMAL"
            )

            active = state_name != "NORMAL"

            junction_status.append(
                JunctionStatus(
                    junction_id=junction_id,
                    state=self.corridor_state_to_number(
                        state_name
                    ),
                    ambulance_count=len(selected) + len(waiting),
                    active=active
                )
            )

        junction_faults = fault_health.get(
            "junction_faults", {}
        )

        process_health = fault_health.get(
            "process_health", {}
        )

        fault_active = bool(junction_faults) or any(
            health != "HEALTHY"
            for health in process_health.values()
        )

        timestamp_ms = int(time.monotonic() * 1000)

        status = SystemStatus(
            ambulance_count=len(ambulance_status),
            ambulances=ambulance_status,
            junction_count=len(junction_status),
            junctions=junction_status,
            fault_active=fault_active,
            current_fault=self.current_fault,
            rejected_packets=self.rejected_packets,
            last_switch_latency_us=self.last_switch_latency_us,
            timestamp_ms=timestamp_ms
        )

        # Keep a Python dictionary for the current dashboard
        # and simulation integration.
        self.latest_status = asdict(status)

        # Extra P6 information that is not part of the
        # shared SystemStatus structure.
        self.latest_status["process_health"] = process_health
        self.latest_status["junction_faults"] = junction_faults
        self.latest_status["active_passages"] = active_passages
        self.latest_status["route_recommendations"] = (
            route_recommendations
        )

        return self.latest_status

    def get_status(self):
        return self.latest_status.copy()


if __name__ == "__main__":

    from priority_scheduler import AmbulanceRequest
    from junction_controller import JunctionController

    print("===== P4 SYSTEM STATUS MANAGER =====")

    ambulances = [
        AmbulanceRequest("AMB01", 1, 3, 40, 20, "NORTH"),
        AmbulanceRequest("AMB02", 1, 1, 60, 10, "EAST"),
        AmbulanceRequest("AMB03", 1, 1, 30, 15, "SOUTH"),
        AmbulanceRequest("AMB04", 4, 2, 25, 30, "WEST")
    ]

    controller = JunctionController()
    junction_results = controller.control_junction(ambulances)

    manager = SystemStatusManager()

    status = manager.generate_status(
        ambulances=ambulances,
        junction_results=junction_results,
        corridor_states={
            1: "AMBULANCE_GREEN",
            4: "AMBULANCE_GREEN"
        },
        active_passages={
            1: {"ambulance_id": "AMB03", "status": "ACTIVE"},
            4: {"ambulance_id": "AMB04", "status": "ACTIVE"}
        },
        fault_health={
            "process_health": {
                "P2": "HEALTHY",
                "P3": "HEALTHY",
                "P5": "HEALTHY"
            },
            "junction_faults": {}
        },
        route_recommendations={}
    )

    print("\nSYSTEM STATUS:")
    print(f"Ambulances monitored: {status['ambulance_count']}")
    print(f"Junctions monitored: {status['junction_count']}")

    for ambulance in status["ambulances"]:
        print(
            f"AMB{ambulance['ambulance_id']:02d} | "
            f"J{ambulance['current_junction_id']} | "
            f"Triage {ambulance['triage_level']} | "
            f"ETA {ambulance['eta_seconds']}s"
        )

    print("\nJUNCTION STATUS:")

    for junction in status["junctions"]:
        print(
            f"J{junction['junction_id']} | "
            f"State: {junction['state']} | "
            f"Ambulances: {junction['ambulance_count']}"
        )

    print("\nPROCESS HEALTH:")
    print(status["process_health"])

    print("\nSystem status generated successfully.")
