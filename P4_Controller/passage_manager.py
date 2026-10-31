
from datetime import datetime


class PassageManager:

    def __init__(self):

        # Stores the ambulance currently using each junction.
        self.active_passages = {}

        # Stores completed ambulance passages.
        self.completed_passages = []

    def activate_corridor(self, junction_id, ambulance_id):

        if junction_id in self.active_passages:

            print(
                f"[REJECTED] J{junction_id} is already occupied by "
                f"{self.active_passages[junction_id]['ambulance_id']}"
            )

            return False

        self.active_passages[junction_id] = {
            "ambulance_id": ambulance_id,
            "status": "ACTIVE",
            "activated_at": datetime.now().isoformat(
                timespec="seconds"
            )
        }

        print(
            f"[CORRIDOR ACTIVE] J{junction_id} assigned to "
            f"{ambulance_id}"
        )

        return True

    def confirm_passage(self, junction_id, ambulance_id):

        passage = self.active_passages.get(junction_id)

        if passage is None:

            print(
                f"[ERROR] No active corridor at J{junction_id}"
            )

            return False

        if passage["ambulance_id"] != ambulance_id:

            print(
                f"[REJECTED] Passage confirmation does not match "
                f"the active ambulance at J{junction_id}"
            )

            return False

        passage["status"] = "PASSED"

        passage["completed_at"] = datetime.now().isoformat(
            timespec="seconds"
        )

        self.completed_passages.append({
            "junction_id": junction_id,
            "ambulance_id": ambulance_id,
            "status": "PASSED",
            "completed_at": passage["completed_at"]
        })

        del self.active_passages[junction_id]

        print(
            f"[PASSAGE CONFIRMED] {ambulance_id} crossed J{junction_id}"
        )

        print(f"[CORRIDOR RELEASED] J{junction_id}")

        return True

    def release_all_active_passages(self):

        if not self.active_passages:
            print("[INFO] No active corridors to release")
            return True

        print("\n===== RELEASING ACTIVE TEST PASSAGES =====")

        # This is a simulation reset only.
        # It must not be used as real passage confirmation.
        for junction_id, passage in list(
            self.active_passages.items()
        ):

            ambulance_id = passage["ambulance_id"]

            print(
                f"[TEST RESET] Releasing J{junction_id} "
                f"from {ambulance_id}"
            )

            del self.active_passages[junction_id]

        return True

    def get_active_passages(self):

        return self.active_passages.copy()

    def get_completed_passages(self):

        return self.completed_passages.copy()


if __name__ == "__main__":

    manager = PassageManager()

    print("===== P4 AMBULANCE PASSAGE MANAGER =====")

    # Test 1: Activate J1.
    manager.activate_corridor(1, "AMB03")

    # Test 2: Reject another ambulance at occupied J1.
    manager.activate_corridor(1, "AMB02")

    # Test 3: Reject incorrect passage confirmation.
    manager.confirm_passage(1, "AMB02")

    # Test 4: Correct passage confirmation.
    manager.confirm_passage(1, "AMB03")

    # Test 5: Activate multiple junctions.
    manager.activate_corridor(1, "AMB01")
    manager.activate_corridor(2, "AMB02")
    manager.activate_corridor(3, "AMB03")
    manager.activate_corridor(4, "AMB04")

    print("\nActive Corridors Before Reset:")
    print(manager.get_active_passages())

    # Test 6: Simulation reset.
    manager.release_all_active_passages()

    print("\nActive Corridors After Reset:")
    print(manager.get_active_passages())

    print("\nCompleted Passages:")
    print(manager.get_completed_passages())
