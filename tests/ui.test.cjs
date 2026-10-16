const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { JSDOM } = require("jsdom");
const base = "src/flashcard_generator/";
const template = fs.readFileSync(base + "templates/index.html", "utf8")
  .replace('{% if ai_available %}hidden{% endif %}', 'data-setup-form')
  .replace(/{%[\s\S]*?%}/g, "").replace(/{{[\s\S]*?}}/g, "")
  .replace(/<link[^>]+>/g, "").replace(/<script[\s\S]*?<\/script>/g, "");
const css = fs.readFileSync(base + "static/app.css", "utf8");
const js = fs.readFileSync(base + "static/app.js", "utf8");
const card = {front:"Define force.", back:"A push or pull.", card_type:"basic", source:"Force is a push or pull."};
const tick = () => new Promise(resolve => setTimeout(resolve, 10));

function app({ storageFails = false, fetch, local = true, aiAvailable = true } = {}) {
  const dom = new JSDOM(template, { url: "http://localhost/", runScripts: "outside-only" });
  const window = dom.window;
  const style = window.document.createElement("style");
  style.textContent = css;
  window.document.head.append(style);
  window.fetch = fetch || (async () => ({ok:true, json: async () => ({cards:[card], mode:"local"})}));
  if (storageFails) Object.defineProperty(window, "localStorage", {get() {throw new Error("Storage disabled");}});
  window.document.querySelector("#api-key-form").hidden = aiAvailable;
  window.eval(js);
  if (local) {
    const mode = window.document.querySelector("#generation-mode");
    mode.value = "local";
    mode.dispatchEvent(new window.Event("change"));
  }
  return { dom, window, $: selector => window.document.querySelector(selector) };
}

test("first-run key is masked, cleared, never stored, and enables generation immediately", async () => {
  const requests = [];
  const secret = "test-secret-key";
  const {dom,window,$} = app({local:false,aiAvailable:false,fetch:async (url,options) => {
    requests.push({url,body:options.body});
    return {ok:true,json:async()=>url === "/api/settings/api-key" ? {ok:true,ai_available:true} :
      url === "/api/jobs" ? {job_id:"new"} : {status:"completed",result:{cards:[card],mode:"ai"}}};
  }});
  assert.equal($("#api-key-form").hidden, false);
  assert.equal($("#api-key").type, "password");
  assert.equal($("#generate-button").disabled, true);
  window.document.dispatchEvent(new window.KeyboardEvent("keydown", {key:"Enter",ctrlKey:true}));
  assert.equal(requests.length, 0);
  $("#api-key").value = secret;
  $("#save-api-key").click();
  assert.equal($("#api-key").value, "");
  assert.equal($("#save-api-key").disabled, true);
  await tick();
  assert.deepEqual(JSON.parse(requests[0].body), {api_key:secret});
  assert.equal($("#api-key-form").hidden, true);
  assert.equal($("#generate-button").disabled, false);
  assert(!window.document.documentElement.outerHTML.includes(secret));
  for (const storage of [window.localStorage,window.sessionStorage]) {
    for (let i = 0; i < storage.length; i++) assert(!storage.getItem(storage.key(i)).includes(secret));
  }
  $("#notes").value = "Force is a push or pull.";
  $("#generate-button").click();
  await tick();
  assert.equal(requests[1].url, "/api/jobs");
  assert.equal($("#card-total").textContent, "1");
  dom.window.close();
});

test("key save failure is private, retryable, and local generation remains available", async () => {
  const secret = "secret-in-server-error";
  const {dom,window,$} = app({local:false,aiAvailable:false,fetch:async () =>
    ({ok:false,json:async()=>({error:secret})})});
  $("#api-key").value = secret;
  $("#save-api-key").click();
  await tick();
  assert.equal($("#api-key").value, "");
  assert.equal($("#api-key-form").hidden, false);
  assert.equal($("#save-api-key").disabled, false);
  assert.equal($("#generate-button").disabled, true);
  assert.match($("#api-key-status").textContent, /Could not reach/);
  assert(!window.document.documentElement.outerHTML.includes(secret));
  $("#generation-mode").value = "local";
  $("#generation-mode").dispatchEvent(new window.Event("change"));
  assert.equal($("#generate-button").disabled, false);
  dom.window.close();
});

test("save errors identify the failing step without displaying server response text", async () => {
  for (const [status,message] of [[400,/format was rejected/],[403,/origin/],
    [404,/missing the Save endpoint/],[405,/missing the Save endpoint/],[500,/could not write/]]) {
    const {dom,$} = app({local:false,aiAvailable:false,fetch:async () =>
      ({ok:false,status,json:async()=>({error:"private-server-text"})})});
    $("#api-key").value = "test-key";
    $("#save-api-key").click();
    await tick();
    assert.match($("#api-key-status").textContent, message);
    assert(!$("#api-key-status").textContent.includes("private-server-text"));
    dom.window.close();
  }
});

test("no promotional headline; review scroll is independent; check always reachable", () => {
  const {dom,window,$} = app();
  assert(!window.document.body.textContent.includes("questions worth remembering"));
  assert.equal(window.getComputedStyle($(".review-scroll")).overflowY, "auto");
  assert.equal(window.getComputedStyle($(".review-scroll")).height, "460px");
  assert.equal($("#study-section").hidden, false);
  dom.window.close();
});

test("AI defaults on, auto count, async results and coverage become stale after edits", async () => {
  const requests = [];
  const coverage = {identified_facts:2,covered_facts:1,sections_processed:1,sections_total:1,requests:5,
    uncovered:[{text:"Pointer size",reason:"Review failed"}]};
  const {dom,window,$} = app({local:false,fetch:async (url,options) => {
    requests.push({url,body:options.body});
    return {ok:true,json:async()=>url === "/api/jobs" ? {job_id:"test"} :
      {status:"completed",result:{cards:[card],mode:"ai",model:"test",coverage}}};
  }});
  assert.equal($("#generation-mode").value, "ai");
  $("#notes").value = "Force is a push or pull.";
  $("#generate-button").click();
  await tick();
  assert.equal(JSON.parse(requests[0].body).max_cards, null);
  assert.equal(requests[1].url, "/api/jobs/test");
  assert.equal($("#coverage-report").hidden, false);
  assert.match($("#coverage-summary").textContent, /1 \/ 2 identified facts/);
  assert.match($("#coverage-gaps").textContent, /Pointer size/);
  assert.equal(window.sessionStorage.getItem("recall-job"), null);
  $(".answer-field textarea").dispatchEvent(new window.Event("input"));
  assert.match($("#coverage-state").textContent, /stale/);
  assert.equal($("#generate-button").disabled, false);
  dom.window.close();
});

test("failed AI job preserves old deck and clearly reports failure", async () => {
  const {dom,$} = app({local:false,fetch:async url => ({ok:true,json:async()=>url === "/api/jobs"
    ? {job_id:"failed"} : {status:"failed",error:"Gemini quota/rate limit reached."}})});
  $("#add-button").click();
  $("#notes").value = "Force is a push or pull.";
  $("#generate-button").click();
  await tick();
  assert.equal($("#card-total").textContent, "1");
  assert.match($("#notice").textContent, /quota.*earlier notes/);
  assert.equal($("#generate-button").disabled, false);
  assert.equal($("#cancel-button").hidden, true);
  dom.window.close();
});

test("generation hides empty state, identifies local rules, and supports 500 cards", async () => {
  const {dom,window,$} = app();
  $("#notes").value = "Force: A push or pull.";
  $("#card-count").value = "500";
  $("#generate-button").click();
  await tick();
  assert.equal(window.getComputedStyle($("#empty-state")).display, "none");
  assert.equal($(".question-field textarea").value, card.front);
  assert.match($("#deck-mode").textContent, /local rules/);
  assert.equal($("#generate-button").disabled, false);
  dom.window.close();
});

test("add inserts at top, resets scroll, focuses question; complete manual card enables export", () => {
  const {dom,window,$} = app();
  $("#add-button").click();
  const question = $(".question-field textarea");
  assert.equal(window.document.activeElement, question);
  question.value = "Manual question";
  question.dispatchEvent(new window.Event("input"));
  $(".answer-field textarea").value = "Manual answer";
  $(".answer-field textarea").dispatchEvent(new window.Event("input"));
  assert.equal($("#export-button").disabled, false);
  $(".review-scroll").scrollTop = 400;
  $("#add-button").click();
  assert.equal($(".question-field textarea").value, "");
  assert.equal(window.document.activeElement, $(".question-field textarea"));
  assert.equal($(".review-scroll").scrollTop, 0);
  dom.window.close();
});

test("storage failures do not break event listeners", () => {
  const {dom,$} = app({storageFails:true});
  $("#add-button").click();
  assert.equal($("#card-total").textContent, "1");
  dom.window.close();
});

test("invalid input and empty results preserve deck; valid generation works afterwards", async () => {
  let response = {cards:[],mode:"local"};
  let ok = false;
  const {dom,$} = app({fetch:async () => ({ok,json:async()=>ok ? response : {error:"Not enough usable text"}})});
  $("#add-button").click();
  $("#notes").value = "asdf";
  $("#generate-button").click();
  await tick();
  assert.equal($("#generate-button").disabled, false);
  assert.equal($("#card-total").textContent, "1");
  ok = true;
  $("#generate-button").click();
  await tick();
  assert.equal($("#card-total").textContent, "1");
  response = {cards:[card],mode:"ai",model:"test-model"};
  $("#notes").value = "Force is a push or pull.";
  $("#generate-button").click();
  await tick();
  assert.match($("#deck-mode").textContent, /Gemini.*test-model/);
  assert.equal($("#generate-button").disabled, false);
  dom.window.close();
});

test("duplicate keyboard submissions do not start duplicate requests", async () => {
  let calls = 0;
  let finish;
  const {dom,window,$} = app({fetch:() => { calls++; return new Promise(resolve => {finish=resolve;}); }});
  $("#notes").value = "Force is a push or pull.";
  const submit = () => window.document.dispatchEvent(new window.KeyboardEvent("keydown", {key:"Enter",ctrlKey:true}));
  submit(); submit();
  assert.equal(calls, 1);
  finish({ok:true,json:async()=>({cards:[card],mode:"local"})});
  await tick();
  assert.equal($("#generate-button").disabled, false);
  dom.window.close();
});

test("request timeout restores controls and preserves manual cards", async () => {
  const {dom,window,$} = app({fetch:(_url, {signal}) => new Promise((_resolve,reject) => {
    signal.addEventListener("abort", () => reject(new window.DOMException("Aborted", "AbortError")));
  })});
  const originalTimer = window.setTimeout.bind(window);
  window.setTimeout = (callback, milliseconds) => originalTimer(callback, milliseconds >= 75000 ? 1 : milliseconds);
  $("#add-button").click();
  $("#notes").value = "Force is a push or pull.";
  $("#generate-button").click();
  await tick();
  assert.equal($("#generate-button").disabled, false);
  assert.equal($("#card-total").textContent, "1");
  assert.match($("#notice").textContent, /timed out/);
  dom.window.close();
});
