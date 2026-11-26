import { apiRequest } from "./api.js";
import { t } from "./i18n.js";
import { applyCopyProtection, renderRichContent } from "./render.js";
import { RunRealtimeClient } from "./sse.js";

const root = document.getElementById("participant-root");
const joinCode = root.dataset.joinCode;
const joinBox = document.getElementById("join-box");
const playBox = document.getElementById("play-box");
const joinForm = document.getElementById("participant-join-form");
const stageEl = document.getElementById("participant-stage");
const timerEl = document.getElementById("participant-timer");
const statusEl = document.getElementById("participant-status");

let runId = "";
let participantToken = "";
let selectedOptions = new Set();
let deadlineMs = null;
let client = null;

async function renderParticipantState(state) {
  applyCopyProtection(state.copy_protection);
  deadlineMs = state.deadline_at ? Date.parse(state.deadline_at) : null;
  stageEl.innerHTML = "";
  statusEl.textContent = "";

  if (state.stage === "lobby") {
    stageEl.textContent = t("waiting");
    return;
  }

  if (state.stage === "playing" && state.substage === "question" && state.question) {
    selectedOptions = new Set();
    const promptBox = document.createElement("div");
    await renderRichContent(promptBox, state.question.prompt || "", state.question.sandbox_html || "");
    stageEl.appendChild(promptBox);

    const grid = document.createElement("div");
    grid.className = "options-grid";
    for (const opt of state.question.options || []) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "option-btn";
      await renderRichContent(btn, opt.text);
      btn.addEventListener("click", () => {
        if (selectedOptions.has(opt.id)) {
          selectedOptions.delete(opt.id);
          btn.classList.remove("selected");
        } else {
          selectedOptions.add(opt.id);
          btn.classList.add("selected");
        }
      });
      grid.appendChild(btn);
    }
    stageEl.appendChild(grid);

    const submitBtn = document.createElement("button");
    submitBtn.type = "button";
    submitBtn.className = "btn";
    submitBtn.style.marginTop = "16px";
    submitBtn.textContent = t("submit");
    submitBtn.addEventListener("click", async () => {
      try {
        await apiRequest(`/api/runs/${runId}/answers`, {
          method: "POST",
          headers: { "X-Participant-Token": participantToken },
          body: JSON.stringify({ selected_options: Array.from(selectedOptions) }),
        });
        statusEl.textContent = t("accepted");
      } catch (err) {
        statusEl.textContent = err.message;
      }
    });
    stageEl.appendChild(submitBtn);
    return;
  }

  if (state.stage === "playing" && state.substage === "question_results") {
    const info = document.createElement("p");
    info.textContent = `${t("score")}: ${state.self_score ?? 0} | ${t("rank")}: ${state.self_rank ?? "-"}`;
    stageEl.appendChild(info);
    if (state.results?.explanation) {
      const exp = document.createElement("div");
      await renderRichContent(exp, state.results.explanation);
      stageEl.appendChild(exp);
    }
    return;
  }

  if (state.stage === "results") {
    const info = document.createElement("h2");
    info.textContent = `${t("final_results")} — ${t("rank")}: ${state.self_rank ?? "-"}, ${t("score")}: ${state.self_score ?? 0}`;
    stageEl.appendChild(info);
  }
}

joinForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const nickname = document.getElementById("nickname-input").value.trim();
  try {
    const joined = await apiRequest(`/api/runs/${encodeURIComponent(joinCode)}/join`, {
      method: "POST",
      body: JSON.stringify({ nickname }),
    });
    runId = joined.run_id;
    participantToken = joined.participant_token;
    joinBox.hidden = true;
    playBox.hidden = false;

    client = new RunRealtimeClient({
      sseUrl: `/api/runs/${runId}/events?role=participant&token=${encodeURIComponent(participantToken)}`,
      pollUrl: `/api/runs/${runId}/state`,
      pollHeaders: { "X-Participant-Token": participantToken },
      onSnapshot: renderParticipantState,
    });
    client.start();
  } catch (err) {
    statusEl.textContent = err.message;
  }
});

setInterval(() => {
  if (!deadlineMs || !client) {
    timerEl.textContent = "";
    return;
  }
  const left = Math.max(0, Math.ceil((deadlineMs - client.nowServerMs()) / 1000));
  timerEl.textContent = `${t("time_left")}: ${left}s`;
}, 200);
