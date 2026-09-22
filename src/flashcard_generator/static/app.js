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
let jobId = null;
let coverage = null;

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
  input.addEventListener("input", () => { onChange(input.value); markCoverageEdited(); updateDeckState(); });
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
  remove.addEventListener("click", () => { cards.splice(index, 1); markCoverageEdited(); renderCards(); });
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
    if (!response.ok) {
      const error = new Error(data.error || "Request failed.");
      error.status = response.status;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Request timed out. Your current deck is unchanged. Try fewer notes/cards.");
    throw error;
  } finally { clearTimeout(timer); }
}
async function generateCards() {
  if (busy) return;
  if (jobId) { showNotice("A generation session is still active. Refresh to reconnect or cancel it first.", true); return; }
  const notes = notesInput.value.trim();
  if (!notes) { showNotice("Paste or import notes first.", true); notesInput.focus(); return; }
  if (!countInput.reportValidity()) return;
  const useAI = modeInput.value === "ai";
  setBusy(true);
  showNotice(useAI ? "Starting coverage audit. Notes are being sent to Google." : "Processing locally. No AI request.");
  try {
    const response = await requestJson(useAI ? "/api/jobs" : "/api/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes, max_cards: countInput.value === "" ? null : Number(countInput.value), use_ai: useAI }),
    });
    if (useAI) {
      jobId = response.job_id;
      if (!jobId) throw new Error("Server did not return a generation session.");
      try { sessionStorage.setItem("recall-job", jobId); } catch {}
      $("#cancel-button").hidden = false;
      await followJob();
    } else {
      applyResult(response);
    }
  } catch (error) {
    showNotice(error.message + " The visible deck is unchanged and may belong to earlier notes.", true);
  } finally {
    setBusy(false);
    $("#cancel-button").hidden = !jobId;
  }
}

function clearJob() {
  jobId = null;
  $("#cancel-button").hidden = true;
  try { sessionStorage.removeItem("recall-job"); } catch {}
}
async function followJob() {
  while (jobId) {
    let state;
    try { state = await requestJson("/api/jobs/" + jobId, {}, 15000); }
    catch (error) { if (error.status === 404) clearJob(); throw error; }
    if (state.status === "completed") {
      clearJob();
      applyResult(state.result);
      return;
    }
    if (["failed", "cancelled"].includes(state.status)) {
      clearJob();
      throw new Error(state.error || "Generation did not complete.");
    }
    showNotice(state.progress || "Processing…");
    await new Promise(resolve => setTimeout(resolve, 1200));
  }
}
function applyResult(data) {
  coverage = data.coverage || null;
  renderCoverage();
  if (!data.cards?.length) {
    showNotice((data.warning || "No supported cards found.") + " The visible deck is unchanged; coverage refers to this new attempt.");
    return;
  }
  cards = data.cards;
  studyIndex = 0;
  showingAnswer = false;
  renderCards();
  reviewScroll.scrollTop = 0;
  $("#deck-mode").textContent = data.mode === "ai" ? "Generated and reviewed by Gemini · " + data.model : "Generated by local rules · no AI";
  showNotice(data.warning || (cards.length + " reviewed cards. Check the source excerpts and coverage report."));
}
function renderCoverage() {
  $("#coverage-report").hidden = !coverage;
  $("#coverage-gaps").replaceChildren();
  if (!coverage) return;
  $("#coverage-summary").textContent = coverage.covered_facts + " / " + coverage.identified_facts +
    " identified facts covered · " + coverage.sections_processed + " / " + coverage.sections_total + " sections processed";
  $("#coverage-state").textContent = "Generation-time audit. " + coverage.requests + " AI requests.";
  const items = [
    ...(coverage.uncovered || []).map(item => item.text + " — " + item.reason),
    ...(coverage.rejected_facts || []).map(item => "Unverified fact: " + item.text + " — " + item.reason),
    ...(coverage.exclusions || []).map(item => "Excluded material in section " + item.section + ": " + item.reason),
  ];
  for (const text of items) {
    const li = document.createElement("li");
    li.textContent = text;
    $("#coverage-gaps").append(li);
  }
}
function markCoverageEdited() {
  if (coverage) $("#coverage-state").textContent = "Deck edited. Coverage counts describe the original generated deck and are now stale.";
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
    ? "Sends notes to Google. Inventories facts, audits omissions, drafts and reviews cards. Multiple requests can take several minutes."
    : "Pattern matching only. No AI review or coverage audit. Nothing is sent to Google.";
});
$("#sample-button").addEventListener("click", () => {
  notesInput.value = "Velocity: The rate of change of displacement.\n\nWhat is the SI unit of force? The SI unit of force is the newton.";
  saveNotes();
});
generateButton.addEventListener("click", generateCards);
$("#export-button").addEventListener("click", exportCsv);
$("#add-button").addEventListener("click", () => {
  markCoverageEdited();
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

$("#cancel-button").addEventListener("click", async () => {
  if (!jobId) return;
  try {
    await requestJson("/api/jobs/" + jobId + "/cancel", {method:"POST"}, 15000);
    showNotice("Cancellation requested. Waiting for the current provider call and any in-flight retry to finish.");
    if (!busy) {
      setBusy(true);
      try { await followJob(); }
      finally { setBusy(false); $("#cancel-button").hidden = !jobId; }
    }
  } catch (error) {
    if (error.status === 404) clearJob();
    showNotice(error.message, true);
  }
});
// Refresh can reconnect to an active job without issuing another paid request.
try { jobId = sessionStorage.getItem("recall-job"); } catch {}
if (jobId) {
  setBusy(true);
  $("#cancel-button").hidden = false;
  followJob().catch(error => showNotice(error.message + " Refresh to reconnect, or cancel before starting again.", true))
    .finally(() => { setBusy(false); $("#cancel-button").hidden = !jobId; });
}
