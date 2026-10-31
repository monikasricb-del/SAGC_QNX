
from priority_scheduler import AmbulanceRequest, PriorityScheduler
from junction_controller import JunctionController
from route_recommender import RouteRecommender

from signal_command import (
    SignalCommandGenerator,
    SIGNAL_RED,
    SIGNAL_GREEN,
    SIGNAL_YELLOW,
    SIGNAL_FLASH_AMBER,
    CORRIDOR_ALL_RED,
    CORRIDOR_AMBULANCE_GREEN
)

from passage_manager import PassageManager
from fault_monitor import FaultMonitor
from system_status import SystemStatusManager
from udp_sender import UDPStatusSender
from udp_decision_receiver import UDPDecisionReceiver
from state_machine import CorridorState, CorridorStateMachine


class P4Controller:

    def __init__(self):
        self.scheduler = PriorityScheduler()
        self.junction_controller = JunctionController()
        self.route_recommender = RouteRecommender()

        # Create receiver, but do not start it automatically.
        self.decision_receiver = UDPDecisionReceiver(
            self.route_recommender,
            on_decision=self.generate_system_status
        )

        self.signal_generator = SignalCommandGenerator()
        self.passage_manager = PassageManager()
        self.fault_monitor = FaultMonitor()
        self.status_manager = SystemStatusManager()
        self.status_sender = UDPStatusSender()

        # Independent state machine for every junction.
        self.junction_states = {
            junction_id: CorridorStateMachine(junction_id)
            for junction_id in range(1, 5)
        }

        self.ambulances = []
        self.junction_results = {}

    def receive_ambulance_requests(self, requests):
        self.ambulances = requests

        print(
            f"\n[P4] Received {len(requests)} ambulance requests"
        )

    def process_priorities(self):
        ranked = self.scheduler.calculate_priority(
            self.ambulances
        )

        print("\n===== PRIORITY RANKING =====")

        for index, ambulance in enumerate(ranked, start=1):
            print(
                f"{index}. {ambulance.ambulance_id} | "
                f"J{ambulance.junction_id} | "
                f"Triage {ambulance.triage_level} | "
                f"ETA {ambulance.eta_seconds}s"
            )

    def process_junctions(self):

        # Identify all unavailable junctions.
        unavailable_junctions = {
            junction_id
            for junction_id in range(1, 5)
            if (
                not self.fault_monitor.is_junction_available(
                    junction_id
                )
                or self.junction_states[junction_id].fault_active
            )
        }

        # Send fault information to the junction controller.
        self.junction_results = (
            self.junction_controller.control_junction(
                self.ambulances,
                unavailable_junctions=unavailable_junctions
            )
        )

        print("\n===== JUNCTION SELECTION =====")

        for junction_id, result in self.junction_results.items():

            print(f"\nJUNCTION J{junction_id}")

            if not result["available"]:
                print("[FAULT] Junction unavailable")

                for ambulance in result["blocked"]:
                    print(
                        f"[BLOCKED] {ambulance.ambulance_id}"
                    )

                continue

            for ambulance in result["selected"]:
                print(
                    f"[SELECTED] {ambulance.ambulance_id}"
                )

            for ambulance in result["waiting"]:
                print(
                    f"[WAITING] {ambulance.ambulance_id}"
                )

    def activate_corridor_states(self):

        print("\n===== CORRIDOR STATE TRANSITIONS =====")

        for junction_id, result in self.junction_results.items():

            if not result["selected"]:
                continue

            state_machine = self.junction_states[junction_id]

            if (
                not self.fault_monitor.is_junction_available(
                    junction_id
                )
                or state_machine.fault_active
            ):
                print(
                    f"[BLOCKED] J{junction_id}: "
                    "Active fault - corridor not activated"
                )
                continue

            # Do not activate another corridor if one is already occupied.
            active_passage = (
                self.passage_manager.get_active_passages().get(
                    junction_id
                )
            )

            if active_passage is not None:
                print(
                    f"[BLOCKED] J{junction_id}: "
                    f"Already occupied by "
                    f"{active_passage['ambulance_id']}"
                )
                continue

            if not state_machine.transition(
                CorridorState.PREPARING
            ):
                continue

            if not state_machine.transition(
                CorridorState.ALL_RED
            ):
                continue

            if not state_machine.transition(
                CorridorState.AMBULANCE_GREEN
            ):
                continue

            ambulance = result["selected"][0]

            activated = self.passage_manager.activate_corridor(
                junction_id,
                ambulance.ambulance_id
            )

            if not activated:
                print(
                    f"[WARNING] J{junction_id}: "
                    "Passage activation failed"
                )

    def generate_signal_commands(self):

        print("\n===== P4 TO P5 JUNCTION SIGNAL COMMANDS =====")

        signal_names = {
            SIGNAL_RED: "RED",
            SIGNAL_YELLOW: "YELLOW",
            SIGNAL_GREEN: "GREEN",
            SIGNAL_FLASH_AMBER: "FLASH AMBER"
        }

        corridor_names = {
            CORRIDOR_ALL_RED: "ALL RED",
            CORRIDOR_AMBULANCE_GREEN: "AMBULANCE GREEN"
        }

        for junction_id, result in self.junction_results.items():

            state_machine = self.junction_states[junction_id]

            available = (
                self.fault_monitor.is_junction_available(
                    junction_id
                )
                and not state_machine.fault_active
            )

            # Only issue GREEN if the passage is actually active.
            active_passage = (
                self.passage_manager.get_active_passages().get(
                    junction_id
                )
            )

            if available and active_passage is not None:
                selected = result["selected"]
            else:
                selected = []

            commands = self.signal_generator.generate_junction_commands(
                junction_id,
                selected,
                result["waiting"]
            )

            for command in commands:

                print(f"\nJUNCTION J{command.junction_id}")
                print(f"Command: {command.command_id}")
                print(f"Ambulance ID: {command.ambulance_id}")
                print(f"Movement ID: {command.movement_id}")

                print(
                    f"NORTH: {signal_names[command.north]} | "
                    f"SOUTH: {signal_names[command.south]} | "
                    f"EAST: {signal_names[command.east]} | "
                    f"WEST: {signal_names[command.west]}"
                )

                print(
                    "Corridor State: "
                    f"{corridor_names.get(command.corridor_state, 'OTHER')}"
                )

                print(
                    f"Command Sequence: {command.command_sequence}"
                )

                print(f"Timestamp: {command.timestamp_ms}")

                if not available:
                    print(
                        "[FAULT RESPONSE] "
                        "P4 generated an ALL-RED command"
                    )

    def receive_passage_confirmation(
        self,
        junction_id,
        ambulance_id
    ):

        confirmed = self.passage_manager.confirm_passage(
            junction_id,
            ambulance_id
        )

        if confirmed:

            state_machine = self.junction_states[junction_id]

            state_machine.transition(CorridorState.CLEARING)
            state_machine.transition(CorridorState.NORMAL)

        return confirmed

    def recover_junction(self, junction_id):

        print(
            f"\n===== JUNCTION J{junction_id} RECOVERY ====="
        )

        if junction_id not in range(1, 5):
            print("[ERROR] Invalid junction ID")
            return False

        state_machine = self.junction_states[junction_id]

        # Check that a fault is actually active.
        if (
            self.fault_monitor.is_junction_available(junction_id)
            or not state_machine.fault_active
        ):
            print(
                "[RECOVERY FAILED] "
                "No matching active fault found"
            )
            return False

        # Clear the fault from the fault monitor.
        fault_cleared = self.fault_monitor.clear_junction_fault(
            junction_id
        )

        if not fault_cleared:
            print(
                "[RECOVERY FAILED] Fault monitor could not clear fault"
            )
            return False

        # Restore the junction state machine.
        state_recovered = state_machine.clear_fault_mode()

        if not state_recovered:
            print("[RECOVERY FAILED] State machine recovery failed")
            return False

        print(
            f"[RECOVERY SUCCESS] J{junction_id} "
            "is available for normal operation"
        )

        return True

    def process_route_recommendation(
        self,
        ambulance_id,
        current_junction,
        destination,
        current_route,
        blocked_junctions
    ):

        return self.route_recommender.recommend_route(
            ambulance_id,
            current_junction,
            destination,
            current_route,
            blocked_junctions
        )

    def generate_system_status(self):

        states = {
            junction_id: machine.state.name
            for junction_id, machine in self.junction_states.items()
        }

        status = self.status_manager.generate_status(
            ambulances=self.ambulances,
            junction_results=self.junction_results,
            corridor_states=states,
            active_passages=self.passage_manager.get_active_passages(),
            fault_health=self.fault_monitor.get_system_health(),
            route_recommendations=(
                self.route_recommender.pending_recommendations
            )
        )

        print("\n===== P6 STATUS DATA =====")

        print(f"Ambulances: {status['ambulance_count']}")
        print(f"Junctions: {status['junction_count']}")

        for junction_id, state in states.items():
            print(f"J{junction_id}: {state}")

        self.status_sender.send_status(status)

        return status

    def run_scenario(self, scenario_name, requests):

        print("\n" + "=" * 55)
        print(f" {scenario_name}")
        print("=" * 55)

        # Reset only junctions without active faults.
        for machine in self.junction_states.values():

            if not machine.fault_active:
                machine.state = CorridorState.NORMAL

        self.receive_ambulance_requests(requests)

        self.process_priorities()
        self.process_junctions()
        self.activate_corridor_states()
        self.generate_signal_commands()
        self.generate_system_status()


if __name__ == "__main__":

    # ==========================================
    # SCENARIO 1 AND SCENARIO 2
    # ==========================================

    p4 = P4Controller()

    # Simulated heartbeat messages.
    p4.fault_monitor.receive_heartbeat("P2")
    p4.fault_monitor.receive_heartbeat("P3")
    p4.fault_monitor.receive_heartbeat("P5")

    # Scenario 1: Four ambulances at J1.
    same_junction_requests = [

        AmbulanceRequest("AMB01", 1, 3, 40, 20, "NORTH"),
        AmbulanceRequest("AMB02", 1, 1, 60, 10, "SOUTH"),
        AmbulanceRequest("AMB03", 1, 1, 30, 15, "EAST"),
        AmbulanceRequest("AMB04", 1, 2, 25, 30, "WEST")

    ]

    p4.run_scenario(
        "SCENARIO 1 - FOUR AMBULANCES AT J1",
        same_junction_requests
    )

    # Simulate P5 confirming AMB03 crossed J1.
    print("\n===== SIMULATED P5 PASSAGE FEEDBACK =====")

    p4.receive_passage_confirmation(1, "AMB03")

    # Scenario 2: Four ambulances distributed across J1-J4.
    distributed_requests = [

        AmbulanceRequest("AMB01", 1, 2, 40, 20, "NORTH"),
        AmbulanceRequest("AMB02", 2, 1, 30, 15, "EAST"),
        AmbulanceRequest("AMB03", 3, 3, 50, 10, "SOUTH"),
        AmbulanceRequest("AMB04", 4, 1, 25, 25, "WEST")

    ]

    p4.run_scenario(
        "SCENARIO 2 - FOUR AMBULANCES DISTRIBUTED",
        distributed_requests
    )

    # ==========================================
    # SCENARIO 3 - J2 FAULT INJECTION
    # ==========================================

    print("\n\n===== SCENARIO 3 - J2 FAULT INJECTION =====")

    fault_p4 = P4Controller()

    # Start only this controller's UDP decision receiver.
    fault_p4.decision_receiver.start()

    fault_p4.fault_monitor.receive_heartbeat("P2")
    fault_p4.fault_monitor.receive_heartbeat("P3")
    fault_p4.fault_monitor.receive_heartbeat("P5")

    # Inject a simulated signal-controller fault at J2.
    fault_p4.fault_monitor.report_junction_fault(
        2,
        "Traffic signal controller not responding"
    )

    fault_p4.junction_states[2].activate_fault_mode()

    fault_requests = [

        AmbulanceRequest("AMB01", 1, 2, 40, 20, "NORTH"),
        AmbulanceRequest("AMB02", 2, 1, 30, 15, "EAST"),
        AmbulanceRequest("AMB03", 3, 3, 50, 10, "SOUTH"),
        AmbulanceRequest("AMB04", 4, 1, 25, 25, "WEST")

    ]

    # Generate an alternative route for AMB01 because J2 is blocked.
    fault_p4.process_route_recommendation(
        ambulance_id="AMB01",
        current_junction=1,
        destination=4,
        current_route=[1, 2, 4],
        blocked_junctions={2}
    )

    fault_p4.run_scenario(
        "SCENARIO 3 - J2 FAULT, OTHER JUNCTIONS HEALTHY",
        fault_requests
    )

    import time
    time.sleep(5)

    # ==========================================
    # SCENARIO 4 - J2 FAULT RECOVERY
    # ==========================================

    print("\n\n===== SCENARIO 4 - J2 FAULT RECOVERY =====")

    # Simulate P5 confirming passage at the healthy junctions
    # from Scenario 3. This releases their active corridors.
    print("\n===== SIMULATED PASSAGE CONFIRMATIONS =====")

    fault_p4.receive_passage_confirmation(1, "AMB01")
    fault_p4.receive_passage_confirmation(3, "AMB03")
    fault_p4.receive_passage_confirmation(4, "AMB04")

    # Recover J2 after the fault.
    fault_p4.recover_junction(2)

    # Run the same distributed scenario again.
    # All four junctions should now be available.
    fault_p4.run_scenario(
        "SCENARIO 4 - ALL JUNCTIONS RECOVERED",
        fault_requests
    )
        # ==========================================
    # KEEP P4 RUNNING FOR DASHBOARD DECISIONS
    # ==========================================

    print("\n[P4] Simulation complete.")
    print("[P4] Waiting for dashboard route decisions...")
    print("[P4] Press CTRL+C to stop P4.")

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[P4] Stopping decision receiver...")

        fault_p4.decision_receiver.close()

        print("[P4] Controller stopped.")
