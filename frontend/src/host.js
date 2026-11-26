import { apiRequest } from "./api.js";
import { RunRealtimeClient } from "./sse.js";

const root = document.getElementById("host-root");
const runId = root.dataset.runId;
const codeEl = document.getElementById("host-code");
const stageEl = document.getElementById("host-stage");
const countsEl = document.getElementById("host-counts");
const broadcastLinkEl = document.getElementById("broadcast-link");
const nextBtn = document.getElementById("btn-next");
const finishBtn = document.getElementById("btn-finish");
const boardBody = document.getElementById("host-leaderboard");

let currentVersion = 1;
let currentStage = "lobby";

function renderState(state) {
  currentVersion = state.version;
  currentStage = state.stage;
  codeEl.textContent = state.join_code;
  stageEl.textContent = `${state.stage} / ${state.substage} (${state.question_index + 1}/${state.total_questions})`;
  countsEl.textContent = `Участников: ${state.participant_count} | Ответов: ${state.answered_count}`;
  broadcastLinkEl.href = `/broadcast/${state.run_id}?token=${encodeURIComponent(state.broadcast_token)}`;

  boardBody.innerHTML = "";
  for (const row of state.leaderboard || []) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${row.rank}</td><td>${row.nickname}</td><td>${row.total_score}</td>`;
    boardBody.appendChild(tr);
  }
}

nextBtn.addEventListener("click", async () => {
  const action = currentStage === "lobby" ? "start" : "next";
  await apiRequest(`/api/runs/${runId}/transition`, {
    method: "POST",
    body: JSON.stringify({ action, expected_version: currentVersion }),
  });
});

finishBtn.addEventListener("click", async () => {
  await apiRequest(`/api/runs/${runId}/transition`, {
    method: "POST",
    body: JSON.stringify({ action: "finish", expected_version: currentVersion }),
  });
});

const client = new RunRealtimeClient({
  sseUrl: `/api/runs/${runId}/events?role=host`,
  pollUrl: `/api/runs/${runId}/host`,
  onSnapshot: renderState,
});
client.start();
