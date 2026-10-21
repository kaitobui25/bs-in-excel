"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { createSensitiveFilter } = require("../addin/sensitive-filter.js");

const settings = {
  enabled: true,
  mask: { keepFirst: 3, keepLast: 1, separator: "..." },
  matchWholeWord: true,
  keywords: ["pokemon", "Pokémon", "casino"]
};

test("mask preserves the first three and last one characters", () => {
  const filter = createSensitiveFilter(settings);
  assert.equal(filter.maskText("pokemon casino"), "pok...n cas...o");
  assert.equal(filter.maskText("POKEMON and Pokémon"), "POK...N and Pok...n");
  assert.equal(filter.maskText("Pokémon POKÉMON"), "Pok...n POK...N");
});

test("Nintendo is included in the configured default keyword list", () => {
  const config = require("../addin/sensitive-words.json");
  assert.ok(config.keywords.includes("nintendo"));
  const filter = createSensitiveFilter(config);
  assert.equal(filter.maskText("Nintendo Switch and POKEMON"), "Nin...o Switch and POK...N");
});

test("regression: Yahoo search snippets mask joined usernames and abbreviated brand names", () => {
  const config = require("../addin/sensitive-words.json");
  const filter = createSensitiveFilter(config);
  const snippets = [
    ["Chính thức của Trung tâm Pokémon (@pokemoncenterPR) / X",
      "Chính thức của Trung tâm Pok...n (@pok...ncenterPR) / X"],
    ["Pokécenter trực tuyến - Instagram", "Pok...r trực tuyến - Instagram"],
    ["phổ biến: pokecenter trực tuyến", "phổ biến: pok...r trực tuyến"],
    ["Kỷ niệm 30 năm Poké Center Online", "Kỷ niệm 30 năm Pok...r Online"],
    ["Danh sách sản phẩmPokemon Center TRỰC TUYẾN. ©Nintendo",
      "Danh sách sản phẩmPok...n Center TRỰC TUYẾN. ©Nin...o"],
    ["https\\://www\\.pokemoncenter-online.com",
      "https\\://www\\.pok...ncenter-online.com"],
    ["https://search.yahoo.co.jp/search?p=pokemon+center+online",
      "https://search.yahoo.co.jp/search?p=pok...n+center+online"],
    ["NintendoSwitch and nintendoswitch", "Nin...oSwitch and nin...oswitch"],
    ["pokecenterPR and PokécenterPR", "pok...rPR and Pok...rPR"]
  ];
  for (const [original, displayed] of snippets) {
    assert.equal(filter.maskText(original), displayed, original);
  }
});

test("compound-word exceptions are opt-in and do not mask arbitrary substrings", () => {
  const config = require("../addin/sensitive-words.json");
  const filter = createSensitiveFilter(config);
  assert.equal(filter.maskText("pokemoncenterPR"), "pok...ncenterPR");
  assert.equal(filter.maskText("pokemon123 prepokemon pokemons"),
    "pokemon123 prepokemon pokemons");
  const withoutCompounds = createSensitiveFilter({ ...config, compoundSuffixes: [] });
  assert.equal(withoutCompounds.maskText("pokemoncenterPR"), "pokemoncenterPR");
  assert.throws(() => createSensitiveFilter({ ...config, compoundSuffixes: "center" }));
  assert.throws(() => createSensitiveFilter({ ...config, compoundSuffixes: [""] }));
});

test("mask URLs, including brands inside domain labels, without changing the input", () => {
  const filter = createSensitiveFilter(settings);
  const original = "https://www.pokemoncenter-online.com/nintendo/products?series=Pokemon";
  assert.equal(filter.maskText(original),
    "https://www.pok...ncenter-online.com/nintendo/products?series=Pok...n");
  assert.equal(original, "https://www.pokemoncenter-online.com/nintendo/products?series=Pokemon");
  assert.equal(filter.maskUrl("https://www.pokemoncenter-online.com"),
    "https://www.pok...ncenter-online.com");
  assert.equal(filter.maskText("www.pokemoncenter-online.com"), "www.pok...ncenter-online.com");
  assert.equal(filter.maskText("pokemoncenter-online.com"), "pok...ncenter-online.com");
  assert.equal(filter.maskText("https\\://www\\.pokemoncenter-online.com"),
    "https\\://www\\.pok...ncenter-online.com");
  assert.equal(filter.maskText("Read https://pokemoncenter-online.com or pokemon game"),
    "Read https://pok...ncenter-online.com or pok...n game");
});

test("distinguishes displayed URLs from prose and CamelCase words", () => {
  const filter = createSensitiveFilter(settings);
  assert.equal(filter.maskText("Danh sách sản phẩmPokemon Center"), "Danh sách sản phẩmPok...n Center");
  assert.equal(filter.maskText("PokemonCenter"), "Pok...nCenter");
  assert.equal(filter.maskText("prePokemon and prepokemon"), "prePok...n and prepokemon");
  assert.equal(filter.maskText("pokemon123"), "pokemon123");
  assert.equal(filter.isUrlText("https://www.pokemoncenter-online.com"), true);
  assert.equal(filter.isUrlText("pokemoncenter-online.com"), true);
  assert.equal(filter.isUrlText("A Pokémon link"), false);
  assert.equal(filter.isUrlText("https://example.com some text"), false);
});

test("handles combining accents and normalized Unicode without losing punctuation", () => {
  const filter = createSensitiveFilter(settings);
  assert.equal(filter.maskText("(Poke\u0301mon), CASINO!"), "(Pok...n), CAS...O!");
  assert.equal(filter.maskText("Ｐｏｋｅｍｏｎ"), "Ｐｏｋ...ｎ");
  assert.equal(filter.maskText("Thích casino và pokemon."), "Thích cas...o và pok...n.");
});

test("matches whole words, not substrings of other words", () => {
  const filter = createSensitiveFilter(settings);
  assert.equal(filter.maskText("pokemon123 prepokemon pokemons _casino"),
    "pokemon123 prepokemon pokemons _casino");
  assert.equal(filter.maskText("anti-pokemon, #casino"), "anti-pok...n, #cas...o");
  assert.equal(filter.maskText("字pokemon字"), "字pokemon字");
});

test("supports optional substring matching, short words and disabling filter", () => {
  const filter = createSensitiveFilter({
    ...settings, keywords: ["ab", "x", "pokemon"], matchWholeWord: false
  });
  assert.equal(filter.maskText("ab x pokemons"), "a... ... pok...ns");
  const disabled = createSensitiveFilter({ ...settings, enabled: false });
  assert.equal(disabled.maskText("pokemon casino"), "pokemon casino");
});

test("rejects invalid config and never changes source text", () => {
  assert.throws(() => createSensitiveFilter({ ...settings, keywords: [""] }));
  assert.throws(() => createSensitiveFilter({ ...settings, mask: { ...settings.mask, keepFirst: -1 } }));
  const original = "Pokémon is here";
  const mask = createSensitiveFilter(settings);
  assert.equal(mask.maskText(original), "Pok...n is here");
  assert.equal(original, "Pokémon is here");
  assert.equal(mask.maskText(""), "");
});
