(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const elements = {
    toolbar: document.querySelector(".toolbar"),
    navToggle: $("nav-toggle"), top: $("scroll-top"), viewport: $("viewport"),
    original: $("translate-original"), translateEn: $("translate-en"),
    translateVi: $("translate-vi"), translateStatus: $("translate-status"),
    address: $("address"), form: $("address-form"), go: $("go"),
    back: $("back"), forward: $("forward"), reload: $("reload"),
    history: $("history"), status: $("status"),
    welcome: $("welcome"), title: $("title"),
    notice: $("page-notice"), content: $("content"), loadMore: $("load-more"),
    links: $("links"), historyList: $("history-list")
  };
  let busy = false;
  let autoLoadEnabled = false;
  let requestVersion = 0;
  let activeRequest = null;
  const expandedPosts = new Set();
  let translationLanguage = null;
  let translationVersion = 0;
  let originalNodes = [];
  const translationControllers = new Set();
  const translationCache = new Map();

  const setStatus = message => { elements.status.textContent = message; };
  const showError = message => {
    setStatus(message);
    elements.notice.textContent = message;
    elements.notice.hidden = false;
  };
  const showOnly = (...visible) => {
    for (const element of [
      elements.welcome, elements.title, elements.notice,
      elements.content, elements.loadMore, elements.links, elements.historyList
    ]) element.hidden = !visible.includes(element);
  };
  const make = (tag, text, className = "") => {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const setBusy = active => {
    busy = active;
    // Navigation is always available: a new action supersedes the old job.
    elements.loadMore.disabled = active;
  };

  function stopTranslation() {
    translationVersion++;
    for (const controller of translationControllers) controller.abort();
    translationControllers.clear();
    elements.translateStatus.textContent = "";
    elements.translateStatus.title = "";
  }

  function updateLanguageButtons() {
    for (const [element, language] of [
      [elements.original, null], [elements.translateEn, "en"], [elements.translateVi, "vi"]
    ]) element.setAttribute("aria-pressed", String(translationLanguage === language));
  }

  // Save the original text nodes so language changes never retranslate a
  // previous translation. Anchors, buttons and image placeholders are intact.
  function captureTextNodes() {
    originalNodes = [];
    for (const root of [elements.title, elements.content, elements.links]) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        if (!node.nodeValue.trim() ||
            node.parentElement.closest(".post-author, .post-toggle, .image-placeholder")) continue;
        originalNodes.push({ node, source: node.nodeValue });
      }
    }
  }

  function splitTranslationText(source) {
    const result = [];
    let chunk = "";
    let encodedLength = 0;
    // Limit URL-encoded length as well as characters: Japanese and Vietnamese
    // can make a query much larger than the original JS string.
    for (const character of source) {
      const size = encodeURIComponent(character).length;
      if (chunk && encodedLength + size > 2600) {
        result.push(chunk);
        chunk = "";
        encodedLength = 0;
      }
      chunk += character;
      encodedLength += size;
    }
    if (chunk) result.push(chunk);
    return result;
  }

  async function translateVisiblePage() {
    stopTranslation();
    for (const { node, source } of originalNodes) node.nodeValue = source;
    if (!translationLanguage || !originalNodes.length || elements.content.hidden) return;
    const version = translationVersion;
    const language = translationLanguage;
    const pending = [];

    for (const { node, source } of originalNodes) {
      const plain = source.trim();
      if (!/[\p{L}]/u.test(plain) || /^https?:\/\/\S+$/.test(plain)) continue;
      const start = source.indexOf(plain);
      const prefix = source.slice(0, start);
      const suffix = source.slice(start + plain.length);
      const pieces = splitTranslationText(plain);
      const translated = pieces.map(part => translationCache.get(language + "\u0000" + part) ?? null);
      const display = () => {
        if (translated.every(value => value !== null)) {
          node.nodeValue = prefix + translated.join("") + suffix;
        }
      };
      display();
      pieces.forEach((text, index) => {
        if (translated[index] === null) pending.push({ text, translated, index, display });
      });
    }

    if (!pending.length) {
      elements.translateStatus.textContent = "Xong";
      updatePostPreviews();
      return;
    }

    const batches = [];
    let batchLength = 0;
    let batchCharacters = 0;
    for (const item of pending) {
      let batch = batches[batches.length - 1];
      const encodedLength = encodeURIComponent(item.text).length;
      if (!batch || batch.length >= 18 || batchLength + encodedLength > 7000 ||
          batchCharacters + item.text.length > 3600) {
        batch = [];
        batches.push(batch);
        batchLength = 0;
        batchCharacters = 0;
      }
      batch.push(item);
      batchLength += encodedLength;
      batchCharacters += item.text.length;
    }

    let next = 0;
    let done = 0;
    let failure = "";
    elements.translateStatus.textContent = "Đang dịch…";
    const worker = async () => {
      while (next < batches.length && !failure && version === translationVersion) {
        const batch = batches[next++];
        const controller = new AbortController();
        translationControllers.add(controller);
        try {
          const response = await fetch("/api/translate", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target: language, texts: batch.map(item => item.text) }),
            signal: controller.signal
          });
          const result = await response.json();
          if (!response.ok || !result.ok || result.texts.length !== batch.length) {
            throw new Error(result.error || "Không thể dịch trang.");
          }
          if (version !== translationVersion) return;
          batch.forEach((item, index) => {
            const trailing = item.text.match(/\s+$/)?.[0] || "";
            const translated = result.texts[index] +
              (trailing && !/\s$/.test(result.texts[index]) ? trailing : "");
            item.translated[item.index] = translated;
            const key = language + "\u0000" + item.text;
            translationCache.set(key, translated);
            if (translationCache.size > 1600) translationCache.delete(translationCache.keys().next().value);
            item.display();
          });
          done += batch.length;
          elements.translateStatus.textContent = `${done}/${pending.length}`;
          updatePostPreviews();
        } catch (error) {
          if (version === translationVersion && error.name !== "AbortError") {
            failure = error.message;
          }
        } finally {
          translationControllers.delete(controller);
        }
      }
    };
    await Promise.all([worker(), worker()]);
    if (version === translationVersion) {
      elements.translateStatus.textContent = failure ? "Lỗi dịch" : "Xong";
      elements.translateStatus.title = failure;
      if (failure) setStatus("Dịch thất bại: " + failure);
    }
  }

  function changeTranslation(language) {
    if (elements.content.hidden) {
      setStatus("Mở một trang trước khi dịch.");
      return;
    }
    translationLanguage = language;
    updateLanguageButtons();
    void translateVisiblePage();
  }

  const parseAddress = input => {
    const raw = input.trim();
    if (!raw) return null;
    if (/^https?:\/\//i.test(raw)) return { action: "navigate", value: raw };
    if (!/\s/.test(raw) && /^(localhost(?::\d+)?|(?:[a-z\d-]+\.)+[a-z\d-]{2,})(?:[/?#:]|$)/i.test(raw)) {
      return { action: "navigate", value: "https://" + raw };
    }
    return { action: "search", value: raw };
  };

  async function request(action, value = "") {
    if (action === "more" && busy) return;
    const version = ++requestVersion;
    if (activeRequest) activeRequest.abort();
    const controller = new AbortController();
    activeRequest = controller;
    // Avoid pinning the auto-hidden toolbar open after keyboard navigation.
    if (elements.toolbar.contains(document.activeElement)) document.activeElement.blur();
    elements.toolbar.classList.remove("pinned-open");
    elements.navToggle.setAttribute("aria-expanded", "false");
    setBusy(true);
    elements.notice.textContent = action === "more" ? "Đang tải thêm bài viết…" : "Đang tải trang…";
    elements.notice.hidden = false;
    // A full-page navigation can take time on Facebook. Clear previously
    // loaded (possibly unfiltered) posts rather than show them below Loading.
    // "more" intentionally keeps the current posts while fetching the rest.
    if (action !== "more") {
      stopTranslation();
      originalNodes = [];
      autoLoadEnabled = false;
      expandedPosts.clear();
      elements.content.replaceChildren();
      elements.links.replaceChildren();
      showOnly(elements.notice);
    }
    setStatus(action === "history" ? "Đang mở lịch sử…" : "Đang tải…");
    let rendered = false;
    let lastPage = null;
    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, value }),
        signal: controller.signal
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "HTTP " + response.status);
      let cursor = 0;
      while (version === requestVersion) {
        const poll = await fetch(`/api/jobs/${data.job_id}?since=${cursor}`, {
          cache: "no-store", signal: controller.signal
        });
        const update = await poll.json();
        if (!poll.ok || !update.ok) throw new Error(update.error || "HTTP " + poll.status);
        if (version !== requestVersion) return;
        cursor = update.version;
        if (update.result) {
          if (update.result.history) showHistory(update.result.history);
          else if (update.result.page) {
            lastPage = update.result.page;
            showPage(lastPage, action === "more" || rendered);
            rendered = true;
          }
        }
        if (update.status === "partial") {
          elements.notice.textContent = "Đang tải tiếp nội dung…";
          elements.notice.hidden = false;
        }
        if (update.status === "complete") break;
        if (update.status === "error") throw new Error(update.error || "Không thể tải trang.");
        if (update.status === "cancelled") break;
        await new Promise(resolve => setTimeout(resolve, 260));
      }
    } catch (error) {
      if (version === requestVersion && error.name !== "AbortError") {
        showError("Lỗi: " + error.message);
      }
    } finally {
      if (version === requestVersion) {
        setBusy(false);
        autoLoadEnabled = Boolean(lastPage && lastPage.has_more &&
          lastPage.blocks?.some(block => block.kind === "post") && !lastPage.notice &&
          elements.notice.hidden);
        activeRequest = null;
      }
    }
  }

  function clickableLink(title, url) {
    const link = make("a", title, "text-link");
    link.href = url;
    link.dataset.nav = "true";
    return link;
  }

  function renderPart(part) {
    if (part.type === "image") {
      const placeholder = part.url ? clickableLink("", part.url) : document.createElement("span");
      placeholder.className = "image-placeholder";
      placeholder.title = "Ảnh đã lọc";
      placeholder.setAttribute("aria-label", "Ảnh đã lọc");
      return placeholder;
    }
    if (part.type === "link" && part.url) {
      return clickableLink(part.text || part.url, part.url);
    }
    return document.createTextNode(part.text || "");
  }

  function renderBlocks(blocks) {
    const fragment = document.createDocumentFragment();
    let postIndex = 0;
    const tagNames = {
      heading: "h2", item: "p", quote: "blockquote",
      code: "pre", caption: "small", paragraph: "p"
    };
    for (const block of blocks) {
      if (block.kind === "anchor") {
        const marker = document.createElement("span");
        marker.className = "anchor-target";
        marker.id = block.id;
        fragment.append(marker);
        continue;
      }
      const kind = Object.prototype.hasOwnProperty.call(tagNames, block.kind)
        ? block.kind : "paragraph";
      const isPost = block.kind === "post";
      const element = document.createElement(isPost ? "section" : tagNames[kind]);
      element.className = "read-block block-" + (isPost ? "post" : kind);
      if (isPost) {
        const key = String(block.key ?? `index:${postIndex}`);
        const author = block.author || "";
        const header = make("div", author || "Bài viết " + (fragment.querySelectorAll(".block-post").length + 1), "post-author");
        const body = make("div", "", "post-body");
        body.id = `post-body-${postIndex++}`;
        element.dataset.postKey = key;
        const expanded = expandedPosts.has(key);
        body.classList.toggle("post-clamped", !expanded);
        const toggle = make("button", expanded ? "See less" : "See more", "post-toggle");
        toggle.type = "button";
        toggle.setAttribute("aria-expanded", String(expanded));
        toggle.setAttribute("aria-controls", body.id);
        toggle.hidden = !expanded;
        const actions = make("div", "", "post-links");
        for (const part of (block.parts || [])) {
          const content = part.type === "text" && author && part.text.startsWith(author + "\n")
            ? { ...part, text: part.text.slice(author.length + 1) } : part;
          (part.type === "link" ? actions : body).append(renderPart(content));
        }
        element.append(header, body, toggle);
        if (actions.childNodes.length) element.append(actions);
      } else {
        for (const part of (block.parts || [])) element.append(renderPart(part));
      }
      fragment.append(element);
    }
    elements.content.replaceChildren(fragment);
  }

  // Check layout only after a render or resize; no mouse/scroll polling.
  function updatePostPreviews() {
    for (const post of elements.content.querySelectorAll(".block-post")) {
      const body = post.querySelector(".post-body");
      const toggle = post.querySelector(".post-toggle");
      if (!body || !toggle) continue;
      const expanded = expandedPosts.has(post.dataset.postKey);
      const truncated = !expanded && body.scrollHeight > body.clientHeight + 1;
      post.classList.toggle("post-collapsed", truncated);
      toggle.hidden = !expanded && !truncated;
    }
  }

  function showPage(page, keepPosition = false) {
    stopTranslation();
    const oldScroll = $("viewport").scrollTop;
    const showTitle = Boolean((page.title || "").trim());
    elements.title.textContent = showTitle ? page.title : "";
    elements.notice.textContent = page.notice || "";
    elements.address.value = page.url;
    const hasBlocks = Array.isArray(page.blocks) && page.blocks.length > 0;
    if (hasBlocks) renderBlocks(page.blocks);
    else elements.content.textContent = page.text || "(Không trích xuất được nội dung văn bản.)";
    elements.links.replaceChildren();
    if (!hasBlocks && page.links.length) {
      elements.links.append(make("h2", "Liên kết (" + page.links.length + ")"));
      const list = document.createElement("ol");
      for (const link of page.links) {
        const item = document.createElement("li");
        item.append(clickableLink(link.title, link.url));
        list.append(item);
      }
      elements.links.append(list);
    }
    showOnly(...(showTitle ? [elements.title] : []), elements.content,
      ...(page.has_more ? [elements.loadMore] : []),
      ...(page.notice ? [elements.notice] : []), ...(hasBlocks ? [] : [elements.links]));
    if (hasBlocks) updatePostPreviews();
    const postCount = hasBlocks ? page.blocks.filter(block => block.kind === "post").length : 0;
    autoLoadEnabled = !busy && postCount > 0 && Boolean(page.has_more) && !page.notice;
    setStatus(postCount
      ? "Đã tải " + postCount + " bài viết · " + (page.text || "").length.toLocaleString("vi-VN") + " ký tự"
      : "Đã tải · " + (page.text || "").length.toLocaleString("vi-VN") + " ký tự · " + page.links.length + " liên kết");
    $("viewport").scrollTop = keepPosition ? oldScroll : 0;
    if (!keepPosition && hasBlocks && page.url.includes("#")) {
      const fragmentId = decodeURIComponent(page.url.split("#")[1] || "");
      const target = document.getElementById(fragmentId);
      if (target) target.scrollIntoView({ block: "start" });
    }
    captureTextNodes();
    if (translationLanguage) void translateVisiblePage();
  }

  function showHistory(entries) {
    stopTranslation();
    originalNodes = [];
    autoLoadEnabled = false;
    elements.historyList.replaceChildren(make("h2", "Lịch sử (" + entries.length + ")"));
    if (!entries.length) elements.historyList.append(make("p", "Chưa có lịch sử."));
    const list = document.createElement("ol");
    for (const entry of entries) {
      const item = document.createElement("li");
      item.append(clickableLink(entry.title || entry.url, entry.url));
      list.append(item);
    }
    elements.historyList.append(list);
    showOnly(elements.historyList);
    setStatus("Chọn một trang trong lịch sử để mở lại.");
    $("viewport").scrollTop = 0;
  }

  elements.form.addEventListener("submit", event => {
    event.preventDefault();
    const command = parseAddress(elements.address.value);
    if (command) request(command.action, command.value);
  });
  $("viewport").addEventListener("click", event => {
    const link = event.target.closest("a[data-nav]");
    if (!link) return;
    event.preventDefault();
    request("navigate", link.href);
  });
  elements.content.addEventListener("click", event => {
    const toggle = event.target.closest("button.post-toggle");
    if (!toggle) return;
    const post = toggle.closest(".block-post");
    const key = post.dataset.postKey;
    const expanded = !expandedPosts.has(key);
    if (expanded) expandedPosts.add(key);
    else expandedPosts.delete(key);
    post.querySelector(".post-body").classList.toggle("post-clamped", !expanded);
    toggle.textContent = expanded ? "See less" : "See more";
    toggle.setAttribute("aria-expanded", String(expanded));
    updatePostPreviews();
  });
  window.addEventListener("resize", updatePostPreviews);
  $("viewport").addEventListener("scroll", () => {
    const view = $("viewport");
    if (busy || !autoLoadEnabled || elements.loadMore.hidden) return;
    if (view.scrollHeight - view.scrollTop - view.clientHeight < 260) {
      autoLoadEnabled = false;
      request("more");
    }
  });
  elements.back.addEventListener("click", () => request("back"));
  elements.top.addEventListener("click", () => elements.viewport.scrollTo({ top: 0, behavior: "smooth" }));
  elements.navToggle.addEventListener("click", () => {
    const open = elements.toolbar.classList.toggle("pinned-open");
    elements.navToggle.setAttribute("aria-expanded", String(open));
    if (open) elements.address.focus();
  });
  elements.original.addEventListener("click", () => changeTranslation(null));
  elements.translateEn.addEventListener("click", () => changeTranslation("en"));
  elements.translateVi.addEventListener("click", () => changeTranslation("vi"));
  elements.forward.addEventListener("click", () => request("forward"));
  elements.reload.addEventListener("click", () => request("reload"));
  elements.history.addEventListener("click", () => request("history"));
  elements.loadMore.addEventListener("click", () => request("more"));
  $("sample-siemens").addEventListener("click", () => request("navigate",
    "https://www.siemens.com/ja-jp/products/tia-portal/"));
  $("sample-facebook").addEventListener("click", () => request("navigate", "https://www.facebook.com/"));
  $("sample-google").addEventListener("click", () => {
    elements.address.value = "siemens tia portal";
    request("search", "siemens tia portal");
  });

  const initialize = () => {
    fetch("/api/health")
      .then(response => response.json())
      .then(data => data.ok
        ? setStatus("Sẵn sàng · nhập URL hoặc tìm Google")
        : showError("Backend không khả dụng"))
      .catch(() => showError("Không kết nối được backend. Kiểm tra launcher."));
  };
  if (typeof Office !== "undefined" && typeof Office.onReady === "function") {
    Office.onReady(initialize);
  } else {
    initialize();
  }
})();
