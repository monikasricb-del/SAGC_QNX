
from priority_scheduler import PriorityScheduler


class JunctionController:

    def __init__(self):
        self.scheduler = PriorityScheduler()

    def control_junction(self, ambulances, unavailable_junctions=None):

        if unavailable_junctions is None:
            unavailable_junctions = set()

        results = {}

        junction_ids = sorted({
            ambulance.junction_id
            for ambulance in ambulances
        })

        for junction_id in junction_ids:

            junction_ambulances = [
                ambulance
                for ambulance in ambulances
                if ambulance.junction_id == junction_id
            ]

            # Check whether this junction has an active fault.
            if junction_id in unavailable_junctions:

                results[junction_id] = {
                    "selected": [],
                    "waiting": [],
                    "blocked": junction_ambulances,
                    "available": False
                }

                continue

            # Rank ambulances at this junction.
            ranked = self.scheduler.calculate_priority(
                junction_ambulances
            )

            # Select only the highest-priority ambulance.
            selected = ranked[:1]
            waiting = ranked[1:]

            results[junction_id] = {
                "selected": selected,
                "waiting": waiting,
                "blocked": [],
                "available": True
            }

        return results


if __name__ == "__main__":

    controller = JunctionController()

    ambulances = [
        # ambulance_id, junction_id, triage, ETA, waiting, approach
        __import__("priority_scheduler").AmbulanceRequest(
            "AMB01", 1, 3, 40, 20, "NORTH"
        ),
        __import__("priority_scheduler").AmbulanceRequest(
            "AMB02", 1, 1, 60, 10, "EAST"
        ),
        __import__("priority_scheduler").AmbulanceRequest(
            "AMB03", 1, 1, 30, 15, "SOUTH"
        ),
        __import__("priority_scheduler").AmbulanceRequest(
            "AMB04", 2, 2, 25, 30, "WEST"
        )
    ]

    # Simulate a fault at J2.
    results = controller.control_junction(
        ambulances,
        unavailable_junctions={2}
    )

    print("===== P4 JUNCTION CONTROLLER TEST =====")

    for junction_id, result in results.items():

        print(f"\nJUNCTION J{junction_id}")

        if not result["available"]:
            print("[FAULT] Junction unavailable")

            for ambulance in result["blocked"]:
                print(f"[BLOCKED] {ambulance.ambulance_id}")

            continue

        for ambulance in result["selected"]:
            print(f"[SELECTED] {ambulance.ambulance_id}")

        for ambulance in result["waiting"]:
            print(f"[WAITING] {ambulance.ambulance_id}")
