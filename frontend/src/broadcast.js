import { renderRichContent } from "./render.js";
import { RunRealtimeClient } from "./sse.js";

const root = document.getElementById("broadcast-root");
const runId = root.dataset.runId;
const token = root.dataset.token;
const stageArea = document.getElementById("broadcast-stage");
const timerEl = document.getElementById("broadcast-timer");
const reactionLayer = document.getElementById("reaction-layer");

let deadlineMs = null;

const client = new RunRealtimeClient({
  sseUrl: `/api/runs/${runId}/events?role=broadcast&token=${encodeURIComponent(token)}`,
  pollUrl: `/api/runs/${runId}/broadcast?token=${encodeURIComponent(token)}`,
  onSnapshot: renderBroadcast,
  onReaction: (data) => {
    const span = document.createElement("span");
    span.textContent = data.emoji || "";
    span.style.marginRight = "8px";
    reactionLayer.appendChild(span);
    setTimeout(() => span.remove(), 2500);
  },
});

async function renderBroadcast(state) {
  deadlineMs = state.deadline_at ? Date.parse(state.deadline_at) : null;
  stageArea.innerHTML = "";

  if (state.stage === "lobby") {
    stageArea.innerHTML = `
      <div class="join-code-huge">${state.join_code}</div>
      <p class="status-msg">Участников: ${state.participant_count}</p>
    `;
    return;
  }

  if (state.stage === "playing" && state.substage === "question" && state.question) {
    const promptBox = document.createElement("div");
    await renderRichContent(promptBox, state.question.prompt || "", state.question.sandbox_html || "");
    stageArea.appendChild(promptBox);

    const grid = document.createElement("div");
    grid.className = "options-grid";
    for (const opt of state.question.options || []) {
      const card = document.createElement("div");
      card.className = "option-btn";
      await renderRichContent(card, opt.text);
      grid.appendChild(card);
    }
    stageArea.appendChild(grid);
    return;
  }

  if (state.stage === "playing" && state.substage === "question_results" && state.results) {
    const title = document.createElement("h2");
    title.textContent = "Результаты вопроса";
    stageArea.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "options-grid";
    for (const opt of state.results.options || []) {
      const card = document.createElement("div");
      card.className = `option-btn ${opt.is_correct ? "correct" : ""}`;
      const count = state.results.stats?.options?.[opt.id] || 0;
      await renderRichContent(card, `${opt.text} (${count})`);
      grid.appendChild(card);
    }
    stageArea.appendChild(grid);
    return;
  }

  if (state.stage === "results") {
    const table = document.createElement("table");
    table.className = "table";
    table.innerHTML = "<thead><tr><th>Место</th><th>Участник</th><th>Баллы</th></tr></thead><tbody></tbody>";
    const tbody = table.querySelector("tbody");
    for (const row of state.leaderboard || []) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${row.rank}</td><td>${row.nickname}</td><td>${row.total_score}</td>`;
      tbody.appendChild(tr);
    }
    stageArea.appendChild(table);
  }
}

setInterval(() => {
  if (!deadlineMs) {
    timerEl.textContent = "";
    return;
  }
  const left = Math.max(0, Math.ceil((deadlineMs - client.nowServerMs()) / 1000));
  timerEl.textContent = `${left}s`;
}, 200);

client.start();
