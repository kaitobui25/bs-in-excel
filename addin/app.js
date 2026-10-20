(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const elements = {
    toolbar: document.querySelector(".toolbar"),
    address: $("address"), form: $("address-form"), go: $("go"),
    back: $("back"), forward: $("forward"), reload: $("reload"),
    history: $("history"), status: $("status"),
    welcome: $("welcome"), title: $("title"),
    notice: $("page-notice"), content: $("content"), loadMore: $("load-more"),
    links: $("links"), historyList: $("history-list")
  };
  let busy = false;
  let autoLoadEnabled = false;
  const expandedPosts = new Set();

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
    for (const button of [elements.go, elements.back, elements.forward, elements.reload, elements.history, elements.loadMore]) {
      button.disabled = active;
    }
    elements.address.disabled = active;
  };

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
    if (busy) return;
    // Avoid pinning the auto-hidden toolbar open after keyboard navigation.
    if (elements.toolbar.contains(document.activeElement)) document.activeElement.blur();
    setBusy(true);
    elements.notice.hidden = true;
    // A full-page navigation can take time on Facebook. Clear previously
    // loaded (possibly unfiltered) posts rather than show them below Loading.
    // "more" intentionally keeps the current posts while fetching the rest.
    if (["navigate", "reload", "search"].includes(action)) {
      autoLoadEnabled = false;
      elements.content.replaceChildren();
      elements.links.replaceChildren();
      showOnly();
    }
    setStatus(action === "history" ? "Đang mở lịch sử…" : "Đang tải…");
    try {
      const response = await fetch("/api/browse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, value })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "HTTP " + response.status);
      if (action !== "more") expandedPosts.clear();
      if (data.history) showHistory(data.history);
      else if (data.page) showPage(data.page, action === "more");
    } catch (error) {
      showError("Lỗi: " + error.message);
    } finally {
      setBusy(false);
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
    autoLoadEnabled = postCount > 0 && Boolean(page.has_more) && !page.notice;
    setStatus(postCount
      ? "Đã tải " + postCount + " bài viết · " + (page.text || "").length.toLocaleString("vi-VN") + " ký tự"
      : "Đã tải · " + (page.text || "").length.toLocaleString("vi-VN") + " ký tự · " + page.links.length + " liên kết");
    $("viewport").scrollTop = keepPosition ? oldScroll : 0;
    if (!keepPosition && hasBlocks && page.url.includes("#")) {
      const fragmentId = decodeURIComponent(page.url.split("#")[1] || "");
      const target = document.getElementById(fragmentId);
      if (target) target.scrollIntoView({ block: "start" });
    }
  }

  function showHistory(entries) {
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
