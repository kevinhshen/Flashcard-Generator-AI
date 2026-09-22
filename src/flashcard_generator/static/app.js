const notesInput = document.querySelector("#notes");
const fileInput = document.querySelector("#notes-file");
const characterCount = document.querySelector("#character-count");
const countInput = document.querySelector("#card-count");
const countValue = document.querySelector("#card-count-value");
const aiToggle = document.querySelector("#ai-toggle");
const generateButton = document.querySelector("#generate-button");
const exportButton = document.querySelector("#export-button");
const addButton = document.querySelector("#add-button");
const sampleButton = document.querySelector("#sample-button");
const cardsContainer = document.querySelector("#cards");
const emptyState = document.querySelector("#empty-state");
const cardTotal = document.querySelector("#card-total");
const notice = document.querySelector("#notice");
const studySection = document.querySelector("#study-section");
const studyCard = document.querySelector("#study-card");
const studySide = document.querySelector("#study-side");
const studyText = document.querySelector("#study-text");
const studyProgress = document.querySelector("#study-progress");

let cards = [];
let studyIndex = 0;
let showingAnswer = false;

const sampleNotes = `Photosynthesis: The process by which plants convert light energy into chemical energy.

Chlorophyll absorbs light most strongly in the blue and red portions of the electromagnetic spectrum. The light-dependent reactions occur in the thylakoid membranes.

Where does the Calvin cycle occur? It occurs in the stroma of the chloroplast.`;

function updateNoteMeta() {
  characterCount.textContent = `${notesInput.value.length.toLocaleString()} characters`;
  localStorage.setItem("recall-notes", notesInput.value);
}

function showNotice(message, isError = false) {
  notice.textContent = message;
  notice.classList.toggle("error", isError);
  notice.hidden = !message;
}

function updateDeckState() {
  cardTotal.textContent = cards.length;
  emptyState.hidden = cards.length > 0;
  exportButton.disabled = cards.length === 0;
  studySection.hidden = cards.length === 0;
  if (studyIndex >= cards.length) studyIndex = Math.max(0, cards.length - 1);
  renderStudyCard();
}

function makeEditor(card, index) {
  const editor = document.createElement("article");
  editor.className = "card-editor";

  const number = document.createElement("span");
  number.className = "card-number";
  number.textContent = String(index + 1).padStart(2, "0");

  const questionField = makeField("QUESTION", card.front, "question-field", (value) => {
    cards[index].front = value;
    renderStudyCard();
  });
  const answerField = makeField("ANSWER", card.back, "answer-field", (value) => {
    cards[index].back = value;
    renderStudyCard();
  });

  const remove = document.createElement("button");
  remove.className = "delete-card";
  remove.type = "button";
  remove.title = "Delete card";
  remove.setAttribute("aria-label", `Delete card ${index + 1}`);
  remove.textContent = "×";
  remove.addEventListener("click", () => {
    cards.splice(index, 1);
    renderCards();
  });

  editor.append(number, questionField, answerField, remove);
  return editor;
}

function makeField(labelText, value, className, onChange) {
  const wrapper = document.createElement("label");
  wrapper.className = className;
  const label = document.createElement("span");
  label.className = "field-label";
  label.textContent = labelText;
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.addEventListener("input", () => onChange(textarea.value));
  wrapper.append(label, textarea);
  return wrapper;
}

function renderCards() {
  cardsContainer.replaceChildren(...cards.map(makeEditor));
  updateDeckState();
}

function renderStudyCard() {
  if (!cards.length) return;
  const card = cards[studyIndex];
  studySide.textContent = showingAnswer ? "ANSWER" : "QUESTION";
  studyText.textContent = showingAnswer ? card.back : card.front;
  studyProgress.textContent = `${studyIndex + 1} / ${cards.length}`;
  studyCard.classList.toggle("answer", showingAnswer);
}

async function generateCards() {
  const notes = notesInput.value.trim();
  if (!notes) {
    showNotice("Paste or import notes before generating a deck.", true);
    notesInput.focus();
    return;
  }

  generateButton.disabled = true;
  generateButton.firstElementChild.textContent = "Generating…";
  showNotice("");
  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        notes,
        max_cards: Number(countInput.value),
        use_ai: aiToggle.checked,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Generation failed.");
    cards = data.cards || [];
    studyIndex = 0;
    showingAnswer = false;
    renderCards();
    if (data.warning) showNotice(data.warning);
    else if (!cards.length) showNotice("No reliable cards were found. Try adding complete sentences or enabling AI mode.");
    else showNotice(`${cards.length} cards generated in ${data.mode === "ai" ? "AI" : "local"} mode.`);
  } catch (error) {
    showNotice(error.message || "Could not generate cards.", true);
  } finally {
    generateButton.disabled = false;
    generateButton.firstElementChild.textContent = "Generate flashcards";
  }
}

function csvEscape(value) {
  return `"${String(value).replaceAll('"', '""')}"`;
}

function exportCsv() {
  const validCards = cards.filter((card) => card.front.trim() && card.back.trim());
  if (!validCards.length) return;
  const rows = ["Front,Back,Type", ...validCards.map((card) => [card.front, card.back, card.card_type || "basic"].map(csvEscape).join(","))];
  const blob = new Blob(["\ufeff" + rows.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `recall-flashcards-${new Date().toISOString().slice(0, 10)}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

notesInput.value = localStorage.getItem("recall-notes") || "";
updateNoteMeta();
updateDeckState();
notesInput.addEventListener("input", updateNoteMeta);
countInput.addEventListener("input", () => { countValue.textContent = countInput.value; });
sampleButton.addEventListener("click", () => { notesInput.value = sampleNotes; updateNoteMeta(); notesInput.focus(); });
generateButton.addEventListener("click", generateCards);
exportButton.addEventListener("click", exportCsv);
addButton.addEventListener("click", () => { cards.push({ front: "", back: "", card_type: "basic" }); renderCards(); });

fileInput.addEventListener("change", async () => {
  const [file] = fileInput.files;
  if (!file) return;
  notesInput.value = await file.text();
  updateNoteMeta();
  showNotice(`Imported ${file.name}.`);
});

studyCard.addEventListener("click", () => { showingAnswer = !showingAnswer; renderStudyCard(); });
document.querySelector("#previous-card").addEventListener("click", () => {
  studyIndex = (studyIndex - 1 + cards.length) % cards.length;
  showingAnswer = false;
  renderStudyCard();
});
document.querySelector("#next-card").addEventListener("click", () => {
  studyIndex = (studyIndex + 1) % cards.length;
  showingAnswer = false;
  renderStudyCard();
});

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    generateCards();
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && cards.length) {
    event.preventDefault();
    exportCsv();
  }
});
