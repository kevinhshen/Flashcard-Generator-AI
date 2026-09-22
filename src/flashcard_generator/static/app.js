const $ = (selector) => document.querySelector(selector);
const notesInput = $("#notes");
const fileInput = $("#notes-file");
const countInput = $("#card-count");
const modeInput = $("#generation-mode");
const generateButton = $("#generate-button");
const cardsContainer = $("#cards");
const reviewScroll = $(".review-scroll");
const notice = $("#notice");
let cards = [];
let studyIndex = 0;
let showingAnswer = false;
let busy = false;

function saveNotes() {
  $("#character-count").textContent = notesInput.value.length.toLocaleString() + " characters";
  // Storage can be disabled or full. This must never disable the rest of the app.
  try { localStorage.setItem("recall-notes", notesInput.value); } catch {}
}
function showNotice(message, error = false) {
  notice.textContent = message;
  notice.classList.toggle("error", error);
  notice.hidden = !message;
}
function setBusy(value) {
  busy = value;
  for (const selector of ["#generate-button", "#import-button", "#sample-button", "#generation-mode", "#card-count", "#add-button"]) {
    $(selector).disabled = value;
  }
  notesInput.readOnly = value;
  cardsContainer.querySelectorAll("textarea, button").forEach((element) => { element.disabled = value; });
  generateButton.firstElementChild.textContent = value ? "Processing…" : "Generate";
  generateButton.setAttribute("aria-busy", String(value));
}
function renderStudyCard() {
  const card = cards[studyIndex];
  $("#study-card").disabled = !card;
  $("#previous-card").disabled = !card;
  $("#next-card").disabled = !card;
  $("#study-progress").textContent = card ? (studyIndex + 1) + " / " + cards.length : "0 / 0";
  $("#study-side").textContent = showingAnswer ? "ANSWER" : "QUESTION";
  $("#study-text").textContent = card ? (showingAnswer ? card.back : card.front) || "(Empty field)" : "Generate or add cards to start.";
  $("#study-card").classList.toggle("answer", showingAnswer);
}
function updateDeckState() {
  $("#card-total").textContent = cards.length;
  $("#empty-state").hidden = cards.length > 0;
  $("#export-button").disabled = !cards.some((card) => card.front.trim() && card.back.trim());
  studyIndex = Math.max(0, Math.min(studyIndex, cards.length - 1));
  renderStudyCard();
}
function makeField(labelText, value, className, onChange) {
  const wrapper = document.createElement("label");
  wrapper.className = className;
  const label = document.createElement("span");
  label.className = "field-label";
  label.textContent = labelText;
  const input = document.createElement("textarea");
  input.value = value;
  input.addEventListener("input", () => { onChange(input.value); updateDeckState(); });
  wrapper.append(label, input);
  return wrapper;
}
function makeEditor(card, index) {
  const editor = document.createElement("article");
  editor.className = "card-editor";
  const number = document.createElement("span");
  number.className = "card-number";
  number.textContent = String(index + 1).padStart(2, "0");
  const question = makeField("QUESTION", card.front, "question-field", (value) => { card.front = value; });
  const answer = makeField("ANSWER", card.back, "answer-field", (value) => { card.back = value; });
  const remove = document.createElement("button");
  remove.className = "delete-card";
  remove.type = "button";
  remove.setAttribute("aria-label", "Delete card " + (index + 1));
  remove.textContent = "×";
  remove.addEventListener("click", () => { cards.splice(index, 1); renderCards(); });
  editor.append(number, question, answer, remove);
  if (card.source) {
    const evidence = document.createElement("details");
    evidence.className = "evidence";
    const label = document.createElement("summary");
    label.textContent = "Source excerpt · compare with your edits";
    const excerpt = document.createElement("p");
    excerpt.textContent = card.source;
    evidence.append(label, excerpt);
    editor.append(evidence);
  }
  return editor;
}
function renderCards() {
  cardsContainer.replaceChildren(...cards.map(makeEditor));
  updateDeckState();
}
async function requestJson(url, options = {}, timeout = 75000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    const data = await response.json().catch(() => ({ error: "The server returned an unreadable response. Restart it and retry." }));
    if (!response.ok) throw new Error(data.error || "Request failed.");
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Request timed out. Your current deck is unchanged. Try fewer notes/cards.");
    throw error;
  } finally { clearTimeout(timer); }
}
async function generateCards() {
  if (busy) return;
  const notes = notesInput.value.trim();
  if (!notes) { showNotice("Paste or import notes first.", true); notesInput.focus(); return; }
  if (!countInput.reportValidity()) return;
  const useAI = modeInput.value === "ai";
  setBusy(true);
  showNotice(useAI ? "Waiting for Gemini. Notes are being sent to Google." : "Processing locally. No AI request.");
  try {
    const data = await requestJson("/api/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes, max_cards: Number(countInput.value), use_ai: useAI }),
    });
    if (!data.cards?.length) {
      showNotice("No supported cards found. Use definitions or explicit Q/A pairs. Your existing deck is unchanged.");
      return;
    }
    cards = data.cards;
    studyIndex = 0;
    showingAnswer = false;
    renderCards();
    reviewScroll.scrollTop = 0;
    $("#deck-mode").textContent = data.mode === "ai" ? "Generated by Gemini · " + data.model : "Generated by local rules · no AI";
    showNotice(data.warning || (cards.length + " cards. Review answers against your notes."));
  } catch (error) {
    showNotice(error.message + " Your existing deck is unchanged.", true);
  } finally { setBusy(false); }
}
function csvEscape(value) { return '"' + String(value).replaceAll('"', '""') + '"'; }
function exportCsv() {
  const valid = cards.filter((card) => card.front.trim() && card.back.trim());
  if (!valid.length) return;
  const rows = ["Front,Back,Type", ...valid.map((card) => [card.front, card.back, card.card_type || "basic"].map(csvEscape).join(","))];
  const url = URL.createObjectURL(new Blob(["\ufeff" + rows.join("\r\n")], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "recall-flashcards-" + new Date().toISOString().slice(0, 10) + ".csv";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  if (valid.length < cards.length) showNotice("Exported " + valid.length + " complete cards; skipped incomplete cards.");
}
try { notesInput.value = localStorage.getItem("recall-notes") || ""; } catch {}
saveNotes();
updateDeckState();
notesInput.addEventListener("input", saveNotes);
modeInput.addEventListener("change", () => {
  $("#mode-help").textContent = modeInput.value === "ai"
    ? "Sends notes to Google. Requires a valid key and quota. Never silently falls back."
    : "Pattern matching only. Nothing is sent to Google.";
});
$("#sample-button").addEventListener("click", () => {
  notesInput.value = "Velocity: The rate of change of displacement.\n\nWhat is the SI unit of force? The SI unit of force is the newton.";
  saveNotes();
});
generateButton.addEventListener("click", generateCards);
$("#export-button").addEventListener("click", exportCsv);
$("#add-button").addEventListener("click", () => {
  cards.unshift({ front: "", back: "", card_type: "basic", source: "" });
  studyIndex = 0;
  showingAnswer = false;
  renderCards();
  reviewScroll.scrollTop = 0;
  cardsContainer.querySelector("textarea").focus({ preventScroll: true });
  if (cards.length === 1) $("#deck-mode").textContent = "Manual deck · no AI";
});
$("#import-button").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", async () => {
  const [file] = fileInput.files;
  if (!file || busy) return;
  setBusy(true);
  showNotice("Reading " + file.name + " locally…");
  try {
    if (file.size > 10 * 1024 * 1024) throw new Error("File exceeds the 10 MB limit.");
    const form = new FormData();
    form.append("file", file);
    const data = await requestJson("/api/import", { method: "POST", body: form }, 30000);
    notesInput.value = data.text;
    saveNotes();
    showNotice(data.warning || ("Imported " + file.name + ". Review the extracted text before generating."));
  } catch (error) { showNotice(error.message, true); }
  finally { fileInput.value = ""; setBusy(false); }
});
$("#study-card").addEventListener("click", () => { showingAnswer = !showingAnswer; renderStudyCard(); });
for (const [selector, offset] of [["#previous-card", -1], ["#next-card", 1]]) {
  $(selector).addEventListener("click", () => {
    if (!cards.length) return;
    studyIndex = (studyIndex + offset + cards.length) % cards.length;
    showingAnswer = false;
    renderStudyCard();
  });
}
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); generateCards(); }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && cards.length) { event.preventDefault(); exportCsv(); }
});
