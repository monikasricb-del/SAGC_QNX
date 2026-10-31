
from enum import IntEnum


class CorridorState(IntEnum):
    NORMAL = 0
    PREPARING = 1
    ALL_RED = 2
    AMBULANCE_GREEN = 3
    CLEARING = 4
    FLASH_AMBER = 5


class CorridorStateMachine:

    def __init__(self, junction_id):

        if junction_id not in range(1, 5):
            raise ValueError("Invalid junction ID")

        self.junction_id = junction_id
        self.state = CorridorState.NORMAL
        self.fault_active = False

    def transition(self, new_state):

        allowed_transitions = {
            CorridorState.NORMAL: [
                CorridorState.PREPARING,
                CorridorState.ALL_RED,
                CorridorState.FLASH_AMBER
            ],

            CorridorState.PREPARING: [
                CorridorState.ALL_RED,
                CorridorState.FLASH_AMBER
            ],

            CorridorState.ALL_RED: [
                CorridorState.AMBULANCE_GREEN,
                CorridorState.FLASH_AMBER
            ],

            CorridorState.AMBULANCE_GREEN: [
                CorridorState.CLEARING,
                CorridorState.ALL_RED,
                CorridorState.FLASH_AMBER
            ],

            CorridorState.CLEARING: [
                CorridorState.NORMAL,
                CorridorState.FLASH_AMBER
            ],

            CorridorState.FLASH_AMBER: [
                CorridorState.NORMAL,
                CorridorState.ALL_RED
            ]
        }

        # Do not allow normal operation while fault is active.
        if (
            self.fault_active
            and new_state not in [
                CorridorState.FLASH_AMBER,
                CorridorState.ALL_RED
            ]
        ):
            print(
                f"[BLOCKED] J{self.junction_id}: "
                "Fault is active"
            )
            return False

        if new_state not in allowed_transitions.get(self.state, []):

            print(
                f"[REJECTED] {self.state.name} -> "
                f"{new_state.name}"
            )

            return False

        previous_state = self.state
        self.state = new_state

        print(
            f"[JUNCTION {self.junction_id}] "
            f"{previous_state.name} -> {self.state.name}"
        )

        return True

    def activate_fault_mode(self):

        self.fault_active = True

        if self.state != CorridorState.FLASH_AMBER:

            previous_state = self.state
            self.state = CorridorState.FLASH_AMBER

            print(
                f"[FAULT] J{self.junction_id}: "
                f"{previous_state.name} -> FLASH_AMBER"
            )

        return True

    def clear_fault_mode(self):

        if not self.fault_active:
            print(f"[INFO] J{self.junction_id}: No active fault")
            return False

        self.fault_active = False

        if self.state == CorridorState.FLASH_AMBER:
            self.state = CorridorState.NORMAL

        print(
            f"[FAULT CLEARED] J{self.junction_id}: "
            f"State is {self.state.name}"
        )

        return True

    def get_status(self):

        return {
            "junction_id": self.junction_id,
            "state": self.state.name,
            "state_code": int(self.state),
            "fault_active": self.fault_active
        }


if __name__ == "__main__":

    junction = CorridorStateMachine(1)

    print("===== NORMAL OPERATION TEST =====")

    junction.transition(CorridorState.PREPARING)
    junction.transition(CorridorState.ALL_RED)
    junction.transition(CorridorState.AMBULANCE_GREEN)
    junction.transition(CorridorState.CLEARING)
    junction.transition(CorridorState.NORMAL)

    print("\n===== FAULT MODE TEST =====")

    junction.activate_fault_mode()

    # This transition must be rejected.
    junction.transition(CorridorState.AMBULANCE_GREEN)

    print("\n===== FAULT RECOVERY TEST =====")

    junction.clear_fault_mode()

    print("\nFinal Status:")
    print(junction.get_status())
