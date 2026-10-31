
from dataclasses import dataclass
from datetime import datetime
import time


# Signal states from shared_corridor.h
SIGNAL_RED = 0
SIGNAL_YELLOW = 1
SIGNAL_GREEN = 2
SIGNAL_FLASH_AMBER = 3

# Corridor states from shared_corridor.h
CORRIDOR_NORMAL = 0
CORRIDOR_PREPARING = 1
CORRIDOR_ALL_RED = 2
CORRIDOR_AMBULANCE_GREEN = 3
CORRIDOR_CLEARING = 4
CORRIDOR_FLASH_AMBER = 5


@dataclass
class SignalCommand:
    junction_id: int
    ambulance_id: int
    movement_id: int
    north: int
    south: int
    east: int
    west: int
    corridor_state: int
    command_sequence: int
    timestamp_ms: int

    # Compatibility properties for the current p4_main.py
    @property
    def command_id(self):
        return f"CMD{self.command_sequence:03d}"

    @property
    def approach(self):
        for direction, state in [
            ("NORTH", self.north),
            ("SOUTH", self.south),
            ("EAST", self.east),
            ("WEST", self.west)
        ]:
            if state == SIGNAL_GREEN:
                return direction
        return "NONE"

    @property
    def signal_state(self):
        return "GREEN" if self.ambulance_id != 0 else "RED"

    @property
    def reason(self):
        if self.ambulance_id == 0:
            return "No ambulance selected - junction held at ALL RED"
        return "Highest priority ambulance selected by P4"


class SignalCommandGenerator:

    def __init__(self):
        self.command_counter = 0

    def ambulance_id_to_number(self, ambulance_id):
        # AMB01 -> 1, AMB02 -> 2, etc.
        if isinstance(ambulance_id, int):
            return ambulance_id

        number = int(ambulance_id.replace("AMB", ""))

        if not 1 <= number <= 4:
            raise ValueError("Invalid ambulance ID")

        return number

    def generate_junction_commands(
        self, junction_id, selected, waiting
    ):

        if junction_id not in range(1, 5):
            raise ValueError("Invalid junction ID")

        if len(selected) > 1:
            raise ValueError(
                "Only one ambulance can be selected per junction"
            )

        # Initially, all four directions remain RED.
        north = SIGNAL_RED
        south = SIGNAL_RED
        east = SIGNAL_RED
        west = SIGNAL_RED

        ambulance_number = 0
        movement_id = 0
        corridor_state = CORRIDOR_ALL_RED

        if selected:
            ambulance = selected[0]

            ambulance_number = self.ambulance_id_to_number(
                ambulance.ambulance_id
            )

            approach = ambulance.approach.upper()

            # Provisional movement IDs.
            # These must be confirmed against the team's
            # final P4 movement configuration.
            movement_ids = {
                "NORTH": 1,
                "SOUTH": 2,
                "EAST": 3,
                "WEST": 4
            }

            if approach not in movement_ids:
                raise ValueError("Invalid ambulance approach")

            movement_id = movement_ids[approach]

            # Only the selected approach receives GREEN.
            if approach == "NORTH":
                north = SIGNAL_GREEN
            elif approach == "SOUTH":
                south = SIGNAL_GREEN
            elif approach == "EAST":
                east = SIGNAL_GREEN
            elif approach == "WEST":
                west = SIGNAL_GREEN

            corridor_state = CORRIDOR_AMBULANCE_GREEN

        self.command_counter += 1

        command = SignalCommand(
            junction_id=junction_id,
            ambulance_id=ambulance_number,
            movement_id=movement_id,
            north=north,
            south=south,
            east=east,
            west=west,
            corridor_state=corridor_state,
            command_sequence=self.command_counter,
            timestamp_ms=int(time.monotonic() * 1000)
        )

        return [command]


if __name__ == "__main__":

    from priority_scheduler import AmbulanceRequest
    from junction_controller import JunctionController

    controller = JunctionController()
    generator = SignalCommandGenerator()

    ambulances = [
        AmbulanceRequest("AMB01", 1, 3, 40, 20, "NORTH"),
        AmbulanceRequest("AMB02", 1, 1, 60, 10, "EAST"),
        AmbulanceRequest("AMB03", 1, 1, 30, 15, "SOUTH"),
        AmbulanceRequest("AMB04", 4, 2, 25, 30, "WEST")
    ]

    results = controller.control_junction(ambulances)

    print("===== P4 TO P5 SIGNAL COMMANDS =====")

    for junction_id, result in results.items():

        commands = generator.generate_junction_commands(
            junction_id,
            result["selected"],
            result["waiting"]
        )

        for command in commands:
            print(f"\nJUNCTION J{command.junction_id}")
            print(f"Command: {command.command_id}")
            print(f"Ambulance ID: {command.ambulance_id}")
            print(f"Movement ID: {command.movement_id}")
            print(
                f"NORTH={command.north} | "
                f"SOUTH={command.south} | "
                f"EAST={command.east} | "
                f"WEST={command.west}"
            )
            print(f"Corridor State: {command.corridor_state}")
            print(f"Sequence: {command.command_sequence}")
            print(f"Timestamp: {command.timestamp_ms}")
