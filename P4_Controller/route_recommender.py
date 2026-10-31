
import heapq
import time


# Route reason codes from shared_corridor.h
ROUTE_REASON_BLOCKED = 1
ROUTE_REASON_HIGH_DELAY = 2
ROUTE_REASON_LOWER_TRAVEL_TIME = 3


class RouteRecommender:

    def __init__(self):

        # Road network: J1-J2, J1-J3, J2-J4, J3-J4.
        # Values represent estimated travel time in seconds.
        self.network = {
            1: {2: 120, 3: 150},
            2: {1: 120, 4: 130},
            3: {1: 150, 4: 110},
            4: {2: 130, 3: 110}
        }

        self.active_routes = {}
        self.pending_recommendations = {}
        self.recommendation_counter = 0

    def validate_junction(self, junction_id):

        if junction_id not in range(1, 5):
            raise ValueError(
                f"Invalid junction ID: {junction_id}"
            )

    def calculate_route(
        self,
        start,
        destination,
        blocked_junctions=None,
        edge_delays=None
    ):

        self.validate_junction(start)
        self.validate_junction(destination)

        blocked_junctions = blocked_junctions or set()
        edge_delays = edge_delays or {}

        if start in blocked_junctions or destination in blocked_junctions:
            return None, float("inf")

        queue = [(0, start, [start])]
        visited = set()

        while queue:

            travel_time, current, path = heapq.heappop(queue)

            if current in visited:
                continue

            visited.add(current)

            if current == destination:
                return path, travel_time

            for neighbour, base_time in self.network[current].items():

                if neighbour in visited:
                    continue

                if neighbour in blocked_junctions:
                    continue

                edge = tuple(sorted((current, neighbour)))
                delay = edge_delays.get(edge, 0)

                if delay < 0:
                    raise ValueError("Edge delay cannot be negative")

                new_time = travel_time + base_time + delay

                heapq.heappush(
                    queue,
                    (new_time, neighbour, path + [neighbour])
                )

        return None, float("inf")

    def calculate_supplied_route_time(
        self,
        route,
        blocked_junctions=None,
        edge_delays=None
    ):

        blocked_junctions = blocked_junctions or set()
        edge_delays = edge_delays or {}

        if not route or len(route) > 4:
            return float("inf")

        if any(junction not in range(1, 5) for junction in route):
            return float("inf")

        total_time = 0

        for index in range(len(route) - 1):

            first = route[index]
            second = route[index + 1]

            if second not in self.network.get(first, {}):
                return float("inf")

            edge = tuple(sorted((first, second)))
            delay = edge_delays.get(edge, 0)

            if delay < 0:
                raise ValueError("Edge delay cannot be negative")

            total_time += self.network[first][second] + delay

        return total_time

    def route_has_high_delay(self, route, edge_delays):

        for index in range(len(route) - 1):

            edge = tuple(sorted((
                route[index],
                route[index + 1]
            )))

            if edge_delays.get(edge, 0) > 0:
                return True

        return False

    def recommend_route(
        self,
        ambulance_id,
        current_junction,
        destination,
        current_route,
        blocked_junctions=None,
        edge_delays=None
    ):

        blocked_junctions = blocked_junctions or set()
        edge_delays = edge_delays or {}

        self.validate_junction(current_junction)
        self.validate_junction(destination)

        if len(blocked_junctions) > 4:
            raise ValueError("Invalid blocked junction list")

        if ambulance_id in self.pending_recommendations:
            print(
                f"[INFO] {ambulance_id}: "
                "A recommendation is already pending"
            )
            return None

        # Calculate current route travel time.
        current_time = self.calculate_supplied_route_time(
            current_route,
            blocked_junctions=set(),
            edge_delays=edge_delays
        )

        # Calculate best available alternative.
        alternative_route, alternative_time = self.calculate_route(
            current_junction,
            destination,
            blocked_junctions,
            edge_delays
        )

        if alternative_route is None:
            print(
                f"[NO ROUTE] {ambulance_id}: "
                "No alternative route is available"
            )
            return None

        if alternative_route == current_route:
            print(
                f"[INFO] {ambulance_id}: "
                "Existing route is still optimal"
            )
            return None

        # Check whether current route contains a blocked junction.
        route_is_blocked = any(
            junction in blocked_junctions
            for junction in current_route
        )

        has_high_delay = self.route_has_high_delay(
            current_route,
            edge_delays
        )

        # Recommend only if blocked or an alternative is faster.
        if not route_is_blocked and alternative_time >= current_time:
            print(
                f"[INFO] {ambulance_id}: "
                "No faster alternative found"
            )
            return None

        # Determine recommendation reason.
        if route_is_blocked:
            reason = ROUTE_REASON_BLOCKED
            reason_text = "Current route contains a blocked junction"

        elif has_high_delay:
            reason = ROUTE_REASON_HIGH_DELAY
            reason_text = "High delay detected on the current route"

        else:
            reason = ROUTE_REASON_LOWER_TRAVEL_TIME
            reason_text = "Alternative route has lower travel time"

        if current_time == float("inf"):
            time_saved = 0
        else:
            time_saved = max(0, current_time - alternative_time)

        self.recommendation_counter += 1

        recommendation = {
            "ambulance_id": ambulance_id,
            "recommendation_id": self.recommendation_counter,
            "reason": reason,
            "reason_text": reason_text,
            "route_count": len(alternative_route),
            "recommended_route": alternative_route,
            "estimated_travel_time_sec": alternative_time,
            "estimated_time_saved_sec": time_saved,
            "timestamp_ms": int(time.monotonic() * 1000),
            "current_route": current_route.copy(),
            "current_time": current_time,
            "recommended_time": alternative_time,
            "status": "PENDING_OPERATOR_APPROVAL"
        }

        self.pending_recommendations[ambulance_id] = recommendation

        print(f"\n[ROUTE RECOMMENDATION] {ambulance_id}")
        print(f"Recommendation ID: {self.recommendation_counter}")
        print(f"Reason: {reason_text}")
        print(f"Current route: {current_route}")
        print(f"Alternative route: {alternative_route}")
        print(f"Current travel time: {current_time} seconds")
        print(f"Alternative travel time: {alternative_time} seconds")
        print(f"Estimated time saved: {time_saved} seconds")
        print("Status: Waiting for operator approval")

        return recommendation

    def decide_route(self, ambulance_id, approved):

        recommendation = self.pending_recommendations.get(
            ambulance_id
        )

        if recommendation is None:
            print("[ERROR] No pending recommendation found")
            return False

        if approved:

            # Update active route ONLY after approval.
            self.active_routes[ambulance_id] = (
                recommendation["recommended_route"].copy()
            )

            recommendation["status"] = "APPROVED"

            print(
                f"[APPROVED] New route activated for {ambulance_id}"
            )

        else:

            # Preserve the original active route.
            recommendation["status"] = "REJECTED"

            print(
                f"[REJECTED] Existing route retained for {ambulance_id}"
            )

        del self.pending_recommendations[ambulance_id]

        return True


if __name__ == "__main__":

    recommender = RouteRecommender()

    print("=" * 55)
    print(" P4 ROUTE RECOMMENDER - APPROVAL AND REJECTION TEST")
    print("=" * 55)

    # ==========================================
    # TEST 1 - OPERATOR APPROVES ALTERNATIVE
    # ==========================================

    print("\n===== TEST 1: OPERATOR APPROVAL =====")

    ambulance_id = "AMB01"
    original_route = [1, 2, 4]

    recommender.active_routes[ambulance_id] = original_route.copy()

    recommender.recommend_route(
        ambulance_id=ambulance_id,
        current_junction=1,
        destination=4,
        current_route=original_route,
        blocked_junctions={2}
    )

    print("\nActive route before decision:")
    print(recommender.active_routes[ambulance_id])

    recommender.decide_route(
        ambulance_id,
        approved=True
    )

    print("\nActive route after approval:")
    print(recommender.active_routes[ambulance_id])

    # ==========================================
    # TEST 2 - OPERATOR REJECTS ALTERNATIVE
    # ==========================================

    print("\n===== TEST 2: OPERATOR REJECTION =====")

    ambulance_id = "AMB02"
    original_route = [1, 2, 4]

    recommender.active_routes[ambulance_id] = original_route.copy()

    recommender.recommend_route(
        ambulance_id=ambulance_id,
        current_junction=1,
        destination=4,
        current_route=original_route,
        blocked_junctions={2}
    )

    print("\nActive route before decision:")
    print(recommender.active_routes[ambulance_id])

    recommender.decide_route(
        ambulance_id,
        approved=False
    )

    print("\nActive route after rejection:")
    print(recommender.active_routes[ambulance_id])

    # ==========================================
    # FINAL VERIFICATION
    # ==========================================

    print("\n===== FINAL TEST RESULTS =====")

    approval_passed = (
        recommender.active_routes["AMB01"] == [1, 3, 4]
    )

    rejection_passed = (
        recommender.active_routes["AMB02"] == [1, 2, 4]
    )

    print(
        "Approval test:",
        "PASSED" if approval_passed else "FAILED"
    )

    print(
        "Rejection test:",
        "PASSED" if rejection_passed else "FAILED"
    )

    print(
        "\nOverall:",
        "ALL TESTS PASSED"
        if approval_passed and rejection_passed
        else "TEST FAILURE"
    )
