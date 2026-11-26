const DICT = {
  ru: {
    waiting: "Ожидание начала квиза",
    question: "Вопрос",
    results: "Результаты",
    final_results: "Итоговая таблица",
    submit: "Отправить ответ",
    accepted: "Ответ принят",
    time_left: "Осталось",
    participants: "Участников",
    score: "Баллы",
    rank: "Место",
  },
  en: {
    waiting: "Waiting for quiz to start",
    question: "Question",
    results: "Results",
    final_results: "Final leaderboard",
    submit: "Submit answer",
    accepted: "Answer accepted",
    time_left: "Time left",
    participants: "Participants",
    score: "Score",
    rank: "Rank",
  },
};

export function getLocale() {
  const saved = localStorage.getItem("nyaquiz_locale");
  if (saved === "ru" || saved === "en") {
    return saved;
  }
  return navigator.language.toLowerCase().startsWith("en") ? "en" : "ru";
}

export function t(key) {
  const loc = getLocale();
  return DICT[loc]?.[key] || DICT.ru[key] || key;
}
