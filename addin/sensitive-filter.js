/* Mask selected words in text nodes, without changing links or source data. */
((host) => {
  "use strict";

  const marks = /\p{M}/gu;
  const wordCharacter = /[\p{L}\p{N}_]/u;
  const regexSpecials = /[.*+?^${}()|[\]\\]/g;
  // Displayed URLs also contain words joined to a domain label (e.g.
  // pokemoncenter-online.com). They need substring matches, unlike prose.
  // The backslash variants occur in escaped URLs shown by some websites.
  const urlPattern = /(?:https?\\?:\/\/|www\\?\.|(?:[\p{L}\d-]+\\?\.)+[\p{L}]{2,})(?:[^\s<>"'()[\]{}]*)/giu;

  function fold(source, offsets = false) {
    let text = "";
    const starts = [];
    const ends = [];
    for (let index = 0; index < source.length;) {
      const character = String.fromCodePoint(source.codePointAt(index));
      const end = index + character.length;
      const normalized = character.normalize("NFKD").replace(marks, "")
        .toLowerCase().replace(/đ/g, "d");
      text += normalized;
      if (offsets) {
        if (!normalized && ends.length) ends[ends.length - 1] = end;
        for (let unit = 0; unit < normalized.length; unit++) {
          starts.push(index);
          ends.push(end);
        }
      }
      index = end;
    }
    return { text, starts, ends };
  }

  function graphemes(text) {
    const result = [];
    for (const character of text) {
      if (/^\p{M}$/u.test(character) && result.length) {
        result[result.length - 1] += character;
      } else {
        result.push(character);
      }
    }
    return result;
  }

  function hideWord(word, mask) {
    const characters = graphemes(word);
    const first = Math.min(mask.keepFirst, Math.max(0, characters.length - 1));
    const last = Math.min(mask.keepLast, Math.max(0, characters.length - first - 1));
    return characters.slice(0, first).join("") + mask.separator +
      (last ? characters.slice(-last).join("") : "");
  }

  function codePointBefore(text, offset) {
    if (offset === 0) return "";
    const prev = text.charCodeAt(offset - 1);
    const start = prev >= 0xDC00 && prev <= 0xDFFF ? offset - 2 : offset - 1;
    return String.fromCodePoint(text.codePointAt(Math.max(0, start)));
  }

  function hasWordBoundary(source, start, end, folded, compoundSuffixes) {
    const before = codePointBefore(folded.text, start);
    const after = end < folded.text.length
      ? String.fromCodePoint(folded.text.codePointAt(end)) : "";
    const originalStart = folded.starts[start];
    const originalEnd = folded.ends[end - 1];
    const originalBefore = codePointBefore(source, originalStart);
    const originalFirst = String.fromCodePoint(source.codePointAt(originalStart));
    const originalAfter = originalEnd < source.length
      ? String.fromCodePoint(source.codePointAt(originalEnd)) : "";
    const originalLast = codePointBefore(source, originalEnd);

    // Some extracted link labels have no separator: "sản phẩmPokemon" or
    // "PokemonCenter". A lower-to-upper transition is still a word boundary.
    const camelStart = /\p{Ll}/u.test(originalBefore) && /\p{Lu}/u.test(originalFirst);
    const camelEnd = /\p{Ll}/u.test(originalLast) && /\p{Lu}/u.test(originalAfter);
    // Recognize explicitly configured joined names, e.g. pokemoncenterPR,
    // without turning off whole-word matching for every other substring.
    const compoundEnd = compoundSuffixes.some(suffix => folded.text.startsWith(suffix, end));
    return (!wordCharacter.test(before) || camelStart) &&
      (!wordCharacter.test(after) || camelEnd || compoundEnd);
  }

  function createSensitiveFilter(settings) {
    if (!settings || typeof settings.enabled !== "boolean" ||
        !Array.isArray(settings.keywords) || settings.keywords.length > 1000 ||
        !settings.mask || !Number.isInteger(settings.mask.keepFirst) ||
        !Number.isInteger(settings.mask.keepLast) ||
        settings.mask.keepFirst < 0 || settings.mask.keepFirst > 20 ||
        settings.mask.keepLast < 0 || settings.mask.keepLast > 20 ||
        typeof settings.mask.separator !== "string" || settings.mask.separator.length > 10 ||
        ![true, false, undefined].includes(settings.matchWholeWord) ||
        (settings.compoundSuffixes !== undefined &&
          (!Array.isArray(settings.compoundSuffixes) || settings.compoundSuffixes.length > 50 ||
           settings.compoundSuffixes.some(suffix =>
             typeof suffix !== "string" || !suffix.trim() || suffix.length > 50))) ||
        settings.keywords.some(term => typeof term !== "string" || !term.trim() || term.length > 100)) {
      throw new Error("Cấu hình bộ lọc từ nhạy cảm không hợp lệ.");
    }
    const keywords = [...new Set(settings.keywords.map(word => fold(word.trim()).text))]
      .sort((a, b) => b.length - a.length);
    const compoundSuffixes = [...new Set((settings.compoundSuffixes || [])
      .map(suffix => fold(suffix.trim()).text))];
    const pattern = settings.enabled && keywords.length
      ? new RegExp(keywords.map(word => word.replace(regexSpecials, "\\$&")).join("|"), "gu")
      : null;

    function mask(source, urlOnly = false) {
      if (!pattern || !source) return source;
      const { text, starts, ends } = fold(source, true);
      const folded = { text, starts, ends };
      // Detect URL-shaped spans once; matching inside them never requires a
      // word boundary. Other text retains the configured whole-word rule.
      const urls = urlOnly ? [] : [...source.matchAll(urlPattern)]
        .map(found => ({ start: found.index, end: found.index + found[0].length }));
      let urlIndex = 0;
      pattern.lastIndex = 0;
      let result = "";
      let cursor = 0;
      for (const found of text.matchAll(pattern)) {
        const offset = found.index;
        const end = offset + found[0].length;
        const originalStart = starts[offset];
        const originalEnd = ends[end - 1];
        while (urlIndex < urls.length && urls[urlIndex].end <= originalStart) urlIndex++;
        const insideUrl = urlOnly || (urlIndex < urls.length &&
          originalStart >= urls[urlIndex].start && originalEnd <= urls[urlIndex].end);
        if (!insideUrl && settings.matchWholeWord !== false &&
            !hasWordBoundary(source, offset, end, folded, compoundSuffixes)) continue;
        if (originalStart < cursor) continue;
        result += source.slice(cursor, originalStart) +
          hideWord(source.slice(originalStart, originalEnd), settings.mask);
        cursor = originalEnd;
      }
      return cursor ? result + source.slice(cursor) : source;
    }
    return Object.freeze({
      maskText: source => mask(source),
      maskUrl: source => mask(source, true),
      isUrlText: source => {
        const hits = [...source.matchAll(urlPattern)];
        return hits.length === 1 && hits[0].index === 0 && hits[0][0].length === source.length;
      }
    });
  }

  host.SensitiveWordFilter = { createSensitiveFilter };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { createSensitiveFilter };
  }
})(typeof window !== "undefined" ? window : globalThis);
