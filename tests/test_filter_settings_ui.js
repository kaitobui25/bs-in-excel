"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { mount, splitKeywords } = require("../addin/filter-settings.js");

function setup(onLoad, onSave) {
  const nodes = new Map();
  for (const id of ["settings-toggle", "settings-menu", "settings-filter",
    "filter-panel", "filter-keywords", "filter-count", "filter-message",
    "filter-save", "filter-cancel"]) {
    const target = new EventTarget();
    target.hidden = ["settings-menu", "filter-panel"].includes(id);
    target.disabled = false;
    target.value = "";
    target.textContent = "";
    target.attributes = {};
    target.setAttribute = (key, value) => { target.attributes[key] = value; };
    target.contains = other => target === other;
    target.focus = () => { target.focused = true; };
    nodes.set(id, target);
  }
  const previousDocument = global.document;
  global.document = { getElementById: id => nodes.get(id), addEventListener() {} };
  mount({ loadSettings: onLoad, saveKeywords: onSave });
  const action = id => nodes.get(id).dispatchEvent(new Event("click"));
  const tick = () => new Promise(resolve => setImmediate(resolve));
  const restore = () => { global.document = previousDocument; };
  return { nodes, action, tick, restore };
}

test("input parser accepts newline-separated phrases and removes blank lines", () => {
  assert.deepEqual(splitKeywords("  pokemon\r\n\n Poké Center \n casino \n"),
    ["pokemon", "Poké Center", "casino"]);
  assert.deepEqual(splitKeywords(""), []);
});

test("Settings -> Filter loads keywords, saves, and reopens server-sorted list", async () => {
  let stored = ["pokemon", "casino"];
  const received = [];
  const ui = setup(async () => ({ keywords: stored }), async words => {
    received.push(words);
    stored = [...new Set(words)].sort((a, b) => a.localeCompare(b, "en"));
    return { keywords: stored };
  });
  try {
    ui.action("settings-toggle");
    assert.equal(ui.nodes.get("settings-menu").hidden, false);
    assert.equal(ui.nodes.get("settings-toggle").attributes["aria-expanded"], "true");
    ui.action("settings-filter");
    await ui.tick();
    assert.equal(ui.nodes.get("filter-panel").hidden, false);
    assert.equal(ui.nodes.get("filter-keywords").value, "pokemon\ncasino");
    assert.equal(ui.nodes.get("filter-save").disabled, false);
    ui.nodes.get("filter-keywords").value = "zoo\nPoké Center\ncasino\n";
    ui.nodes.get("filter-keywords").dispatchEvent(new Event("input"));
    assert.equal(ui.nodes.get("filter-count").textContent, "3 từ");
    ui.action("filter-save");
    await ui.tick();
    assert.deepEqual(received[0], ["zoo", "Poké Center", "casino"]);
    assert.equal(ui.nodes.get("filter-keywords").value, "casino\nPoké Center\nzoo");
    assert.match(ui.nodes.get("filter-message").textContent, /Đã lưu 3 từ/);
    ui.action("filter-cancel");
    assert.equal(ui.nodes.get("filter-panel").hidden, true);
    ui.action("settings-toggle");
    ui.action("settings-filter");
    await ui.tick();
    assert.equal(ui.nodes.get("filter-keywords").value, "casino\nPoké Center\nzoo");
  } finally {
    ui.restore();
  }
});

test("save failure does not claim success or clear the editor", async () => {
  const ui = setup(async () => ({ keywords: ["casino"] }),
    async () => { throw new Error("disk full"); });
  try {
    ui.action("settings-filter");
    await ui.tick();
    ui.nodes.get("filter-keywords").value = "new word";
    ui.action("filter-save");
    await ui.tick();
    assert.match(ui.nodes.get("filter-message").textContent, /disk full/);
    assert.equal(ui.nodes.get("filter-keywords").value, "new word");
    assert.equal(ui.nodes.get("filter-save").disabled, false);
  } finally {
    ui.restore();
  }
});
