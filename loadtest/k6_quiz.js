import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";

const deliveryLatency = new Trend("state_delivery_latency_ms");

export const options = {
  scenarios: {
    participants: {
      executor: "constant-vus",
      vus: 500,
      duration: "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    state_delivery_latency_ms: ["p(95)<500"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8080";
const JOIN_CODE = __ENV.JOIN_CODE || "TEST01";

export default function () {
  const joinRes = http.post(
    `${BASE_URL}/api/runs/${JOIN_CODE}/join`,
    JSON.stringify({ nickname: `user_${__VU}_${__ITER}` }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(joinRes, { "joined ok": (r) => r.status === 200 });
  if (joinRes.status !== 200) {
    sleep(1);
    return;
  }

  const joined = joinRes.json();
  const headers = {
    "Content-Type": "application/json",
    "X-Participant-Token": joined.participant_token,
  };

  const t0 = Date.now();
  const stateRes = http.get(`${BASE_URL}/api/runs/${joined.run_id}/state`, { headers });
  deliveryLatency.add(Date.now() - t0);
  check(stateRes, { "state ok": (r) => r.status === 200 });

  http.post(
    `${BASE_URL}/api/runs/${joined.run_id}/answers`,
    JSON.stringify({ selected_options: ["a"] }),
    { headers }
  );

  http.post(
    `${BASE_URL}/api/runs/${joined.run_id}/reactions`,
    JSON.stringify({ emoji: "fire" }),
    { headers }
  );

  sleep(1.5);
}
