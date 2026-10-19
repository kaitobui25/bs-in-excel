(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const elements = {
    address: $("address"), form: $("address-form"), go: $("go"),
    back: $("back"), forward: $("forward"), reload: $("reload"),
    history: $("history"), status: $("status"),
    welcome: $("welcome"), title: $("title"), url: $("page-url"),
    content: $("content"), links: $("links"), historyList: $("history-list")
  };
  let busy = false;

  const setStatus = message => { elements.status.textContent = message; };
  const showOnly = (...visible) => {
    for (const element of [
      elements.welcome, elements.title, elements.url,
      elements.content, elements.links, elements.historyList
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
    for (const button of [elements.go, elements.back, elements.forward, elements.reload, elements.history]) {
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
    setBusy(true);
    setStatus(action === "history" ? "Đang mở lịch sử…" : "Đang tải…");
    try {
      const response = await fetch("/api/browse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, value })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "HTTP " + response.status);
      if (data.history) showHistory(data.history);
      else if (data.page) showPage(data.page);
    } catch (error) {
      setStatus("Lỗi: " + error.message);
    } finally {
      setBusy(false);
      elements.address.focus();
    }
  }

  function clickableLink(title, url) {
    const button = make("button", title, "text-link");
    button.type = "button";
    button.title = url;
    button.addEventListener("click", () => {
      if (title === "Mở Google trong trình duyệt ngoài") {
        if (typeof Office !== "undefined" && Office.context?.ui?.openBrowserWindow) {
          Office.context.ui.openBrowserWindow(url);
        } else {
          window.open(url, "_blank", "noopener");
        }
      } else {
        request("navigate", url);
      }
    });
    return button;
  }

  function showPage(page) {
    elements.title.textContent = page.title || "Không có tiêu đề";
    elements.url.textContent = page.url;
    elements.address.value = page.url;
    elements.content.textContent = page.text || "(Không trích xuất được nội dung văn bản.)";
    elements.links.replaceChildren();
    if (page.links.length) {
      elements.links.append(make("h2", "Liên kết (" + page.links.length + ")"));
      const list = document.createElement("ol");
      for (const link of page.links) {
        const item = document.createElement("li");
        item.append(clickableLink(link.title, link.url));
        list.append(item);
      }
      elements.links.append(list);
    }
    showOnly(elements.title, elements.url, elements.content, elements.links);
    setStatus("Đã tải · " + (page.text || "").length.toLocaleString("vi-VN") + " ký tự · " + page.links.length + " liên kết");
    $("viewport").scrollTop = 0;
  }

  function showHistory(entries) {
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
  elements.back.addEventListener("click", () => request("back"));
  elements.forward.addEventListener("click", () => request("forward"));
  elements.reload.addEventListener("click", () => request("reload"));
  elements.history.addEventListener("click", () => request("history"));
  $("sample-siemens").addEventListener("click", () => request("navigate",
    "https://www.siemens.com/ja-jp/products/tia-portal/"));
  $("sample-google").addEventListener("click", () => {
    elements.address.value = "siemens tia portal";
    request("search", "siemens tia portal");
  });

  const initialize = () => {
    fetch("/api/health")
      .then(response => response.json())
      .then(data => setStatus(data.ok ? "Sẵn sàng · nhập URL hoặc tìm Google" : "Backend không khả dụng"))
      .catch(() => setStatus("Không kết nối được backend. Kiểm tra launcher."));
    elements.address.focus();
  };
  if (typeof Office !== "undefined" && typeof Office.onReady === "function") {
    Office.onReady(initialize);
  } else {
    initialize();
  }
})();
