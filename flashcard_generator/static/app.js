(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const notes = $("#notes");
  const cardsContainer = $("#cards");
  const cardTemplate = $("#card-template");
  const results = $("#results");
  const notice = $("#notice");
  const state = { cards: [] };
  const draftKey = "study-cards-draft-v1";

  const example = `Accounting: Accounting is a process that collects, records, and reports information to decision makers.

Private accountants: for business

Investors and creditors are the main external users of accounting information.`;

  function selectedEngine() {
    return document.querySelector("input[name=engine]:checked").value;
  }

  function settings() {
    return {
      engine: selectedEngine(),
      polish: $("#polish").value,
      device: $("#device").value,
      offline: $("#offline").checked,
      modelId: window.STUDY_CARDS_CONFIG.defaultModel,
    };
  }

  function updateWordCount() {
    const count = notes.value.trim() ? notes.value.trim().split(/\s+/).length : 0;
    $("#word-count").textContent = `${count.toLocaleString()} word${count === 1 ? "" : "s"}`;
  }

  function saveDraft() {
    localStorage.setItem(draftKey, notes.value);
    updateWordCount();
  }

  function showNotice(message) {
    notice.textContent = message;
    notice.classList.remove("hidden");
  }

  function clearNotice() {
    notice.textContent = "";
    notice.classList.add("hidden");
  }

  async function request(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({ error: "The local server returned an invalid response." }));
    if (!response.ok) throw new Error(data.error || "Something went wrong.");
    return data;
  }

  async function generate() {
    if (!notes.value.trim()) {
      notes.focus();
      showNotice("Paste notes or import a .txt file before generating cards.");
      return;
    }
    const button = $("#generate-button");
    button.disabled = true;
    button.firstElementChild.textContent = "Generating…";
    clearNotice();
    try {
      const data = await request("/api/generate", { notes: notes.value, ...settings() });
      state.cards = data.cards;
      results.classList.remove("hidden");
      $("#results-summary").textContent = `${data.summary.accepted} cards ready · ${data.summary.rejected + data.summary.skipped} safely skipped`;
      $("#ai-filter").checked = selectedEngine() !== "rules";
      renderCards();
      results.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      results.classList.remove("hidden");
      showNotice(error.message);
    } finally {
      button.disabled = false;
      button.firstElementChild.textContent = "Generate flashcards";
    }
  }

  function readCard(cardElement) {
    const id = cardElement.dataset.id;
    const card = state.cards.find((item) => item.id === id);
    if (!card) return null;
    card.front = $(".card-front", cardElement).value.trim();
    card.back = $(".card-back", cardElement).value.trim();
    return card;
  }

  function renderCards() {
    cardsContainer.replaceChildren();
    const onlyAi = $("#ai-filter").checked;
    const visibleCards = state.cards.filter((card) => !onlyAi || card.generator === "flan");
    $("#empty-results").classList.toggle("hidden", visibleCards.length !== 0);

    visibleCards.forEach((card) => {
      const fragment = cardTemplate.content.cloneNode(true);
      const element = fragment.querySelector(".card");
      element.dataset.id = card.id;
      element.classList.toggle("ai-card", card.generator === "flan");
      $(".badge", element).textContent = card.generator === "flan" ? "AI review" : card.kind === "cloze" ? "Cloze" : "Rule";
      $(".card-front", element).value = card.front;
      $(".card-back", element).value = card.back;
      $(".source-text", element).textContent = card.sourceText;
      const regenerate = $(".regenerate-button", element);
      regenerate.classList.toggle("hidden", card.generator !== "flan");
      regenerate.addEventListener("click", () => regenerateCard(element));
      $(".delete-button", element).addEventListener("click", () => {
        state.cards = state.cards.filter((item) => item.id !== card.id);
        renderCards();
      });
      $(".card-front", element).addEventListener("input", () => readCard(element));
      $(".card-back", element).addEventListener("input", () => readCard(element));
      cardsContainer.append(fragment);
    });
  }

  async function regenerateCard(element) {
    const card = readCard(element);
    if (!card || !card.front || !card.back) {
      showNotice("A card needs both a question and answer before it can be regenerated.");
      return;
    }
    const button = $(".regenerate-button", element);
    button.disabled = true;
    button.textContent = "…";
    clearNotice();
    try {
      const data = await request("/api/regenerate", { card, ...settings() });
      const index = state.cards.findIndex((item) => item.id === card.id);
      state.cards[index] = data.card;
      renderCards();
    } catch (error) {
      showNotice(error.message);
    } finally {
      button.disabled = false;
      button.textContent = "↻";
    }
  }

  function exportTsv() {
    const validCards = state.cards.filter((card) => card.front.trim() && card.back.trim());
    if (!validCards.length) {
      showNotice("Generate or keep at least one complete card before exporting.");
      return;
    }
    const escape = (value) => String(value).replaceAll("\t", " ").replaceAll("\r\n", " ").replaceAll("\n", " ");
    const tsv = validCards.map((card) => `${escape(card.front)}\t${escape(card.back)}`).join("\n");
    const file = new Blob([tsv], { type: "text/tab-separated-values;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(file);
    link.download = "flashcards.tsv";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function updateEngineUi() {
    const ai = selectedEngine() !== "rules";
    $("#ai-settings").classList.toggle("hidden", !ai);
    document.querySelectorAll(".engine-option").forEach((label) => {
      label.classList.toggle("selected", label.querySelector("input").checked);
    });
  }

  $("#generate-button").addEventListener("click", generate);
  $("#export-button").addEventListener("click", exportTsv);
  $("#ai-filter").addEventListener("change", renderCards);
  notes.addEventListener("input", saveDraft);
  document.querySelectorAll("input[name=engine]").forEach((input) => input.addEventListener("change", updateEngineUi));
  $("#example-button").addEventListener("click", () => { notes.value = example; saveDraft(); notes.focus(); });
  $("#clear-button").addEventListener("click", () => { notes.value = ""; $("#file-name").textContent = ""; saveDraft(); notes.focus(); });
  $("#note-file").addEventListener("change", async (event) => {
    const [file] = event.target.files;
    if (!file) return;
    if (file.size > 1_000_000) { showNotice("Choose a text file smaller than 1 MB."); return; }
    try {
      notes.value = await file.text();
      $("#file-name").textContent = file.name;
      saveDraft();
    } catch {
      showNotice("That file could not be read as text.");
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.key === "Enter") { event.preventDefault(); generate(); }
    if (event.ctrlKey && event.key.toLowerCase() === "s") { event.preventDefault(); exportTsv(); }
  });

  notes.value = localStorage.getItem(draftKey) || "";
  updateWordCount();
  updateEngineUi();
})();
