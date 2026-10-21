/* Small, dependency-free settings panel. Server is the source of truth. */
((host) => {
  "use strict";

  function splitKeywords(text) {
    return text.split(/\r?\n/u).map(line => line.trim()).filter(Boolean);
  }

  function mount({ loadSettings, saveKeywords }) {
    const $ = id => document.getElementById(id);
    const trigger = $("settings-toggle");
    const menu = $("settings-menu");
    const filterItem = $("settings-filter");
    const panel = $("filter-panel");
    const editor = $("filter-keywords");
    const count = $("filter-count");
    const message = $("filter-message");
    const save = $("filter-save");
    const cancel = $("filter-cancel");
    let busy = false;
    let openVersion = 0;

    const closeMenu = () => {
      menu.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    };
    const updateCount = () => {
      count.textContent = `${splitKeywords(editor.value).length} từ`;
    };
    const setBusy = value => {
      busy = value;
      editor.disabled = value;
      save.disabled = value;
      cancel.disabled = value;
    };
    const closePanel = () => {
      if (busy) return;
      openVersion++;
      panel.hidden = true;
      message.textContent = "";
      trigger.focus();
    };

    trigger.addEventListener("click", () => {
      menu.hidden = !menu.hidden;
      trigger.setAttribute("aria-expanded", String(!menu.hidden));
    });
    filterItem.addEventListener("click", async () => {
      closeMenu();
      const version = ++openVersion;
      panel.hidden = false;
      message.textContent = "Đang tải danh sách…";
      setBusy(true);
      try {
        const settings = await loadSettings();
        if (version !== openVersion) return;
        editor.value = settings.keywords.join("\n");
        updateCount();
        message.textContent = "";
        setBusy(false);
        editor.focus();
      } catch (error) {
        if (version !== openVersion) return;
        message.textContent = "Lỗi: " + error.message;
        // Allow Cancel, but not an accidental overwrite after a failed load.
        busy = false;
        cancel.disabled = false;
      }
    });
    editor.addEventListener("input", () => {
      updateCount();
      message.textContent = "";
    });
    cancel.addEventListener("click", closePanel);
    save.addEventListener("click", async () => {
      if (busy) return;
      const keywords = splitKeywords(editor.value);
      setBusy(true);
      message.textContent = "Đang lưu…";
      try {
        const settings = await saveKeywords(keywords);
        editor.value = settings.keywords.join("\n");
        updateCount();
        message.textContent = `Đã lưu ${settings.keywords.length} từ (A–Z).`;
      } catch (error) {
        message.textContent = "Lỗi lưu: " + error.message;
      } finally {
        setBusy(false);
      }
    });
    document.addEventListener("pointerdown", event => {
      if (!trigger.contains(event.target) && !menu.contains(event.target)) closeMenu();
    });
    document.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      if (!panel.hidden && !busy) {
        closePanel();
        event.preventDefault();
      } else if (!menu.hidden) {
        closeMenu();
        trigger.focus();
        event.preventDefault();
      }
    });
  }

  host.ReaderFilterSettings = { mount, splitKeywords };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { mount, splitKeywords };
  }
})(typeof window !== "undefined" ? window : globalThis);
