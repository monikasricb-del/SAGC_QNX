
const API_URL = "/api/status";
const DECISION_URL = "/api/route-decision";

let latestStatus = null;
const decisionMessages = {};

function getDirection(value) {
    const directions = {
        1: "North",
        2: "South",
        3: "East",
        4: "West"
    };

    return directions[value] || "Unknown";
}

function getJunctionState(value) {
    const states = {
        0: "NORMAL",
        1: "PREPARING",
        2: "ALL RED",
        3: "AMBULANCE GREEN",
        4: "CLEARING",
        5: "FLASH AMBER"
    };

    return states[value] || "UNKNOWN";
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}

// Ambulance monitoring
function displayAmbulances(data) {
    const container = document.getElementById("ambulance-container");

    if (!container) return;

    if (!data || data.length === 0) {
        container.innerHTML = "<p>No ambulance data available.</p>";
        return;
    }

    container.innerHTML = data.map(ambulance => `
        <div class="monitor-card">
            <h3>AMB${String(ambulance.ambulance_id).padStart(2, "0")}</h3>
            <p>Current Junction: J${ambulance.current_junction_id}</p>
            <p>Next Junction: J${ambulance.next_junction_id}</p>
            <p>Direction: ${getDirection(ambulance.approach_direction)}</p>
            <p>Triage Level: ${ambulance.triage_level}</p>
            <p>ETA: ${ambulance.eta_seconds} seconds</p>
            <p>Status Code: ${ambulance.status}</p>
            <p>Diversion Pending: ${ambulance.diversion_pending ? "Yes" : "No"}</p>
        </div>
    `).join("");
}

// Junction monitoring
function displayJunctions(data, faults = {}) {
    const container = document.getElementById("junction-container");

    if (!container) return;

    if (!data || data.length === 0) {
        container.innerHTML = "<p>No junction data available.</p>";
        return;
    }

    container.innerHTML = data.map(junction => {
        const id = String(junction.junction_id);
        const state = getJunctionState(junction.state);
        const fault = faults[id];

        const faultStatus = fault ? "FAULT DETECTED" : "NORMAL";

        let signal = "RED";

        if (junction.state === 3) {
            signal = "GREEN";
        } else if (junction.state === 5) {
            signal = "FLASH AMBER";
        }

        const corridor = junction.state === 3 ? "ACTIVE" : "INACTIVE";

        return `
            <div class="monitor-card">
                <h3>J${junction.junction_id}</h3>
                <p>Signal: <strong>${signal}</strong></p>
                <p>Corridor: ${corridor}</p>
                <p>State: ${state}</p>
                <p>Ambulance Count: ${junction.ambulance_count}</p>
                <p>Fault Status: <strong>${faultStatus}</strong></p>
                ${fault ? `<p>Fault Reason: ${escapeHTML(fault.reason)}</p>` : ""}
            </div>
        `;
    }).join("");
}

// Component health monitoring
function displayComponents(health) {
    const container = document.getElementById("component-container");

    if (!container) return;

    const componentNames = {
        P1: "Ambulance Simulator",
        P2: "Communication Module",
        P3: "Fault Monitor",
        P4: "Priority Controller",
        P5: "Traffic Signal Controller",
        P6: "Dashboard"
    };

    container.innerHTML = Object.entries(componentNames).map(([id, name]) => {
        let status = "Not Reported";

        if (id === "P4" || id === "P6") {
            status = "Online";
        } else if (health && health[id]) {
            status = health[id];
        }

        return `
            <div class="monitor-card">
                <h3>${id} - ${name}</h3>
                <p>Status: <strong>${escapeHTML(status)}</strong></p>
            </div>
        `;
    }).join("");
}

// Update overview cards
function updateOverview(data) {
    const cards = document.querySelectorAll(".cards .card");

    if (cards.length >= 4) {
        cards[0].querySelector("p").textContent = data.ambulance_count;
        cards[1].querySelector("p").textContent = data.junction_count;

        const activeCount = (data.junctions || []).filter(
            junction => junction.state === 3
        ).length;

        cards[2].querySelector("p").textContent = activeCount;

        cards[3].querySelector("p").textContent =
            data.fault_active ? "FAULT DETECTED" : "NORMAL";
    }
}

// Display live route recommendations from P4
function displayRouteRecommendations(recommendations) {
    const container = document.getElementById("route-container");

    if (!container) return;

    const entries = Object.entries(recommendations || {});

    if (entries.length === 0) {
        container.innerHTML = "<p>No pending route recommendations.</p>";
        return;
    }

    container.innerHTML = entries.map(([ambulanceId, recommendation]) => {
        const recommendationId = recommendation.recommendation_id;

        const currentRoute = (recommendation.current_route || [])
            .map(junction => `J${junction}`)
            .join(" → ");

        const suggestedRoute = (recommendation.recommended_route || [])
            .map(junction => `J${junction}`)
            .join(" → ");

        const messageKey = `${ambulanceId}-${recommendationId}`;
        const message = decisionMessages[messageKey] || "Pending Operator Approval";

        return `
            <div class="monitor-card">
                <h3>${escapeHTML(ambulanceId)} - Route Recommendation</h3>

                <p><strong>Recommendation ID:</strong> ${recommendationId}</p>

                <p><strong>Reason:</strong>
                    ${escapeHTML(recommendation.reason_text)}
                </p>

                <p><strong>Current Route:</strong>
                    ${escapeHTML(currentRoute)}
                </p>

                <p><strong>Suggested Route:</strong>
                    ${escapeHTML(suggestedRoute)}
                </p>

                <p><strong>Current Travel Time:</strong>
                    ${recommendation.current_time} seconds
                </p>

                <p><strong>Suggested Travel Time:</strong>
                    ${recommendation.estimated_travel_time_sec} seconds
                </p>

                <p><strong>Estimated Time Saved:</strong>
                    ${recommendation.estimated_time_saved_sec} seconds
                </p>

                <p><strong>Status:</strong>
                    <span>${escapeHTML(message)}</span>
                </p>

                <div class="route-buttons">
                    <button
                        class="accept-btn"
                        data-action="APPROVE"
                        data-ambulance="${escapeHTML(ambulanceId)}"
                        data-recommendation="${recommendationId}">
                        Accept Route
                    </button>

                    <button
                        class="reject-btn"
                        data-action="REJECT"
                        data-ambulance="${escapeHTML(ambulanceId)}"
                        data-recommendation="${recommendationId}">
                        Reject Route
                    </button>
                </div>
            </div>
        `;
    }).join("");

    // Connect the buttons to the Flask API.
    container.querySelectorAll("button[data-action]").forEach(button => {
        button.addEventListener("click", () => {
            sendRouteDecision(
                button.dataset.ambulance,
                Number(button.dataset.recommendation),
                button.dataset.action
            );
        });
    });
}

// Send approval or rejection to P4 through Flask
async function sendRouteDecision(ambulanceId, recommendationId, action) {
    const messageKey = `${ambulanceId}-${recommendationId}`;

    if (decisionMessages[messageKey] === "Decision sent. Waiting for P4.") {
        return;
    }

    decisionMessages[messageKey] = "Sending decision...";

    displayRouteRecommendations(
        latestStatus?.route_recommendations || {}
    );

    try {
        const response = await fetch(DECISION_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                ambulance_id: ambulanceId,
                recommendation_id: recommendationId,
                action: action
            })
        });

        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Decision could not be sent");
        }

        decisionMessages[messageKey] =
            "Decision sent. Waiting for P4.";

        console.log(
            `[P6] ${action} sent for ${ambulanceId}`
        );

        displayRouteRecommendations(
            latestStatus?.route_recommendations || {}
        );

    } catch (error) {
        decisionMessages[messageKey] = "Failed: " + error.message;

        console.error("[P6] Route decision error:", error);

        displayRouteRecommendations(
            latestStatus?.route_recommendations || {}
        );
    }
}

// Fetch live status from P4
async function fetchP4Status() {
    try {
        const response = await fetch(API_URL, {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error("Unable to fetch P4 status");
        }

        const data = await response.json();

        if (!data || data.ambulance_count === undefined) {
            console.log("Waiting for P4 status data...");
            return;
        }

        latestStatus = data;

        displayAmbulances(data.ambulances || []);

        displayJunctions(
            data.junctions || [],
            data.junction_faults || {}
        );

        displayComponents(data.process_health || {});

        displayRouteRecommendations(
            data.route_recommendations || {}
        );

        updateOverview(data);

    } catch (error) {
        console.error(
            "[P6 Dashboard] Connection error:",
            error.message
        );
    }
}

// Start dashboard
fetchP4Status();

// Refresh live data every second
setInterval(fetchP4Status, 1000);
