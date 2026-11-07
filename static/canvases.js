const list = document.getElementById("list");
const emptyText = document.getElementById("empty");

async function api(path, method = "GET", body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const response = await fetch(path, options);
  if (response.status === 401) {
    location.href = "/login";
    return null;
  }
  return response.json();
}

function showCanvas(canvas) {
  const item = document.createElement("li");

  const link = document.createElement("a");
  link.href = `/canvas/${canvas.id}`;
  link.textContent = canvas.title;

  const renameButton = document.createElement("button");
  renameButton.textContent = "Переименовать";
  renameButton.addEventListener("click", async () => {
    const title = prompt("Новое название", canvas.title)?.trim();
    if (title) {
      const updated = await api(`/api/canvases/${canvas.id}`, "PATCH", { title });
      if (updated) {
        canvas.title = updated.title;
        link.textContent = updated.title;
      }
    }
  });

  const deleteButton = document.createElement("button");
  deleteButton.textContent = "Удалить";
  deleteButton.addEventListener("click", async () => {
    if (confirm(`Удалить холст «${canvas.title}» со всеми блоками?`)) {
      await api(`/api/canvases/${canvas.id}`, "DELETE");
      item.remove();
      emptyText.hidden = list.children.length > 0;
    }
  });

  item.append(link, renameButton, deleteButton);
  list.append(item);
}

async function loadPage() {
  const me = await api("/api/me");
  if (!me) {
    return;
  }
  document.getElementById("user").textContent = me.login;

  const canvases = await api("/api/canvases");
  canvases.forEach(showCanvas);
  emptyText.hidden = canvases.length > 0;
}

document.getElementById("create").addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = document.getElementById("title").value.trim();
  const canvas = await api("/api/canvases", "POST", { title });
  if (canvas) {
    location.href = `/canvas/${canvas.id}`;
  }
});

document.getElementById("logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  location.href = "/login";
});

loadPage();
