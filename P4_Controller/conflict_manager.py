
from dataclasses import dataclass


@dataclass
class AmbulanceMovement:
    ambulance_id: str
    junction_id: int
    approach: str
    exit_direction: str


class ConflictManager:

    # Opposite approaches travelling straight are compatible.
    # Crossing movements and movements from the same approach
    # are treated as conflicting in this initial model.

    def are_conflicting(self, ambulance_a, ambulance_b):

        if ambulance_a.junction_id != ambulance_b.junction_id:
            return False

        if ambulance_a.approach == ambulance_b.approach:
            return True

        opposite = {
            "NORTH": "SOUTH",
            "SOUTH": "NORTH",
            "EAST": "WEST",
            "WEST": "EAST"
        }

        # Opposite approaches travelling straight through
        # are allowed together in this simplified model.
        if (
            opposite[ambulance_a.approach] == ambulance_b.approach
            and opposite[ambulance_a.exit_direction] == ambulance_b.exit_direction
        ):
            return False

        return True

    def check_conflicts(self, ambulances):

        conflicts = []

        for i in range(len(ambulances)):
            for j in range(i + 1, len(ambulances)):

                first = ambulances[i]
                second = ambulances[j]

                if self.are_conflicting(first, second):
                    conflicts.append({
                        "junction": first.junction_id,
                        "ambulance_1": first.ambulance_id,
                        "ambulance_2": second.ambulance_id,
                        "status": "CONFLICT"
                    })

        return conflicts


if __name__ == "__main__":

    manager = ConflictManager()

    movements = [
        AmbulanceMovement("AMB01", 1, "NORTH", "SOUTH"),
        AmbulanceMovement("AMB02", 1, "EAST", "WEST"),
        AmbulanceMovement("AMB03", 2, "NORTH", "EAST"),
        AmbulanceMovement("AMB04", 1, "SOUTH", "EAST")
    ]

    print("===== P4 JUNCTION CONFLICT MANAGER =====")

    conflicts = manager.check_conflicts(movements)

    if conflicts:
        for conflict in conflicts:
            print(
                f"J{conflict['junction']}: "
                f"{conflict['ambulance_1']} vs "
                f"{conflict['ambulance_2']} - "
                f"{conflict['status']}"
            )
    else:
        print("No conflicting movements detected.")
