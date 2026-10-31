
from dataclasses import dataclass


@dataclass
class AmbulanceRequest:
    ambulance_id: str
    junction_id: int
    triage_level: int
    eta_seconds: float
    waiting_seconds: float
    approach: str


class PriorityScheduler:

    def calculate_priority(self, ambulances):

        if len(ambulances) > 4:
            raise ValueError("Maximum 4 ambulances are supported")

        for ambulance in ambulances:
            if not 1 <= ambulance.triage_level <= 5:
                raise ValueError("Triage level must be between 1 and 5")

            if ambulance.eta_seconds < 0 or ambulance.waiting_seconds < 0:
                raise ValueError("ETA and waiting time cannot be negative")

        ranked_ambulances = sorted(
            ambulances,
            key=lambda ambulance: (
                ambulance.triage_level,
                ambulance.eta_seconds,
                -ambulance.waiting_seconds
            )
        )

        return ranked_ambulances

    def select_highest_priority(self, ambulances):

        ranked = self.calculate_priority(ambulances)

        if not ranked:
            return None

        return ranked[0]


if __name__ == "__main__":

    scheduler = PriorityScheduler()

    ambulances = [
        AmbulanceRequest("AMB01", 1, 3, 40, 20, "NORTH"),
        AmbulanceRequest("AMB02", 1, 1, 60, 10, "SOUTH"),
        AmbulanceRequest("AMB03", 1, 1, 30, 15, "EAST"),
        AmbulanceRequest("AMB04", 1, 2, 25, 30, "WEST")
    ]

    print("===== P4 PRIORITY SCHEDULER =====")

    ranked = scheduler.calculate_priority(ambulances)

    print("\nAmbulance Priority Ranking:")

    for position, ambulance in enumerate(ranked, start=1):
        print(
            f"{position}. {ambulance.ambulance_id} | "
            f"Junction: J{ambulance.junction_id} | "
            f"Triage: {ambulance.triage_level} | "
            f"ETA: {ambulance.eta_seconds}s | "
            f"Waiting: {ambulance.waiting_seconds}s"
        )

    selected = scheduler.select_highest_priority(ambulances)

    print("\nSelected Ambulance:")
    print(selected.ambulance_id)
