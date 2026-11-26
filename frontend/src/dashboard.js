import { apiRequest, convertImageToCleanWebp } from "./api.js";
import { renderRichContent } from "./render.js";

const listEl = document.getElementById("quiz-list");
const createForm = document.getElementById("quiz-form");
const promptInput = document.getElementById("q-prompt");
const previewEl = document.getElementById("latex-preview");
const ocrInput = document.getElementById("formula-photo-input");
const statusEl = document.getElementById("dashboard-status");

async function loadQuizzes() {
  try {
    const quizzes = await apiRequest("/api/quizzes");
    listEl.innerHTML = "";
    for (const quiz of quizzes) {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <h3>${quiz.title}</h3>
        <p class="status-msg">${quiz.questions.length} вопросов</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn" data-launch="${quiz.id}">Запустить квиз</button>
          <button class="btn btn-secondary" data-delete="${quiz.id}">В корзину</button>
        </div>
      `;
      listEl.appendChild(card);
    }
  } catch (err) {
    if (err.status === 401) {
      window.location.href = "/auth";
      return;
    }
    statusEl.textContent = err.message;
  }
}

listEl.addEventListener("click", async (ev) => {
  const launchId = ev.target.dataset.launch;
  const deleteId = ev.target.dataset.delete;
  if (launchId) {
    const run = await apiRequest("/api/runs", {
      method: "POST",
      body: JSON.stringify({ quiz_id: launchId }),
    });
    window.location.href = `/host/${run.run_id}`;
  } else if (deleteId) {
    await apiRequest(`/api/quizzes/${deleteId}`, { method: "DELETE" });
    await loadQuizzes();
  }
});

promptInput.addEventListener("input", () => {
  renderRichContent(previewEl, promptInput.value);
});

ocrInput.addEventListener("change", async () => {
  const file = ocrInput.files?.[0];
  if (!file) {
    return;
  }
  statusEl.textContent = "Распознавание формулы...";
  try {
    const cleanFile = await convertImageToCleanWebp(file);
    const fd = new FormData();
    fd.append("file", cleanFile);
    const res = await apiRequest("/api/ai/latex-from-photo", {
      method: "POST",
      body: fd,
    });
    promptInput.value = `${promptInput.value} $$${res.latex}$$`.trim();
    await renderRichContent(previewEl, promptInput.value);
    statusEl.textContent = "Формула добавлена";
  } catch (err) {
    statusEl.textContent = err.message;
  }
});

createForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const title = document.getElementById("quiz-title").value.trim();
  const prompt = promptInput.value.trim();
  const optA = document.getElementById("opt-a").value.trim();
  const optB = document.getElementById("opt-b").value.trim();
  const correctOpt = document.getElementById("opt-correct").value;
  try {
    await apiRequest("/api/quizzes", {
      method: "POST",
      body: JSON.stringify({
        title,
        description: "",
        questions: [
          {
            id: "q1",
            prompt,
            explanation: document.getElementById("q-explanation").value.trim(),
            options: [
              { id: "a", text: optA, is_correct: correctOpt === "a" },
              { id: "b", text: optB, is_correct: correctOpt === "b" },
            ],
            duration_seconds: Number(document.getElementById("q-duration").value || 30),
          },
        ],
      }),
    });
    createForm.reset();
    previewEl.innerHTML = "";
    await loadQuizzes();
  } catch (err) {
    statusEl.textContent = err.message;
  }
});

loadQuizzes();
