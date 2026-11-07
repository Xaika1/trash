const BLOCK_NAMES = {
  1: "Начало/конец",
  2: "Процесс",
  3: "Решение",
  4: "Данные",
};

const INK = "#2b2b2b";
const ORANGE = "#ff7a1a";
const RED = "#d93a2b";

const BLOCK_COLORS = {
  1: { top: "#ffb26b", bottom: "#ff7a1a", border: "#c95200", text: "#1a1a1a" },
  2: { top: "#ffffff", bottom: "#e4e4e4", border: "#4a4a4a", text: "#1a1a1a" },
  3: { top: "#ffe08a", bottom: "#f5b82e", border: "#a97800", text: "#1a1a1a" },
  4: { top: "#b5ece6", bottom: "#4cc2b8", border: "#12756e", text: "#0d2b28" },
};
const SIDES = [0, 1, 2, 3];

const stageBox = document.getElementById("stage");
const statusText = document.getElementById("status");
const editor = document.getElementById("editor");
const deleteBar = document.getElementById("delete-bar");
const deleteInfo = document.getElementById("delete-info");
const deleteNext = document.getElementById("delete-next");
const confirmWindow = document.getElementById("confirm");
const confirmText = document.getElementById("confirm-text");
const editTools = document.getElementById("edit-tools");
const zoomValue = document.getElementById("zoom-value");
const toast = document.getElementById("toast");
const titleText = document.getElementById("title");
const roleText = document.getElementById("role");
const sharePanel = document.getElementById("share");
const accessSelect = document.getElementById("access");
const closedWindow = document.getElementById("closed");
const closedText = document.getElementById("closed-text");
const typeSelect = document.getElementById("block-type");
const peopleButton = document.getElementById("people-button");
const peopleList = document.getElementById("people-list");

const ROLE_NAMES = {
  owner: "Вы владелец",
  edit: "Можно редактировать",
  view: "Только просмотр",
};

const PEOPLE_ROLES = {
  owner: "владелец",
  edit: "редактирует",
  view: "смотрит",
};

const stage = new Konva.Stage({
  container: "stage",
  width: stageBox.clientWidth,
  height: stageBox.clientHeight,
  draggable: true,
});

const edgeLayer = new Konva.Layer();
const blockLayer = new Konva.Layer();
const frameLayer = new Konva.Layer();
stage.add(edgeLayer, blockLayer, frameLayer);

const blocks = new Map();
const edges = new Map();
const blocksToDelete = new Set();
const edgesToDelete = new Set();

let socket = null;
let canvasId = null;
let shareLink = "";
let canEdit = false;
let closed = false;
let selectedBlock = null;
let selectedEdge = null;
let editing = null;
let toastTimer = null;
let deleteMode = false;
let newLine = null;
let linkStart = null;
let lastMoveTime = 0;
let frame = null;
let frameUsed = false;

function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(message);
  }
}

function getSocketAddress() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const [, page, value] = location.pathname.split("/");
  const param = page === "share" ? "code" : "canvas";
  return `${protocol}://${location.host}/ws?${param}=${encodeURIComponent(value)}`;
}

function connect() {
  socket = new WebSocket(getSocketAddress());

  socket.onopen = () => {
    clearCanvas();
    statusText.textContent = "Подключено";
    statusText.classList.remove("offline");
  };

  socket.onmessage = (event) => {
    handleMessage(event.data);
  };

  socket.onclose = (event) => {
    if (event.code === 4401) {
      location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
      return;
    }
    if (event.code === 4403 || event.code === 4404) {
      showClosed(closed ? closedText.textContent : "Холст не найден или доступ закрыт");
      return;
    }
    statusText.textContent = "Нет связи, переподключаемся…";
    statusText.classList.add("offline");
    setTimeout(connect, 2000);
  };
}

function handleMessage(message) {
  const parts = message.split(";");
  const command = parts[0];

  if (command === "I") {
    handleInfo(parts[1], parts.slice(2).join(";"));
  }

  if (command === "C") {
    showClosed(parts.slice(1).join(";"));
  }

  if (command === "W") {
    showMessage(parts.slice(1).join(";"));
  }

  if (command === "P") {
    showPeople(parts.slice(1).join(";"));
  }

  if (command === "N") {
    drawBlock({
      id: Number(parts[1]),
      type: Number(parts[2]),
      x: Number(parts[3]),
      y: Number(parts[4]),
      w: Number(parts[5]),
      h: Number(parts[6]),
      text: parts.slice(7).join(";"),
    });
  }

  if (command === "M") {
    moveBlockSmoothly(Number(parts[1]), Number(parts[2]), Number(parts[3]));
  }

  if (command === "X") {
    removeBlock(Number(parts[1]));
  }

  if (command === "E") {
    drawEdge({
      id: Number(parts[1]),
      from: Number(parts[2]),
      fromSide: Number(parts[3]),
      to: Number(parts[4]),
      toSide: Number(parts[5]),
      label: parts.slice(6).join(";"),
    });
  }

  if (command === "D") {
    removeEdge(Number(parts[1]));
  }
}

function handleInfo(name, value) {
  if (name === "id") {
    canvasId = Number(value);
  }
  if (name === "title") {
    titleText.textContent = value;
    document.title = value;
  }
  if (name === "role") {
    setRole(value);
  }
  if (name === "access") {
    accessSelect.value = value;
  }
  if (name === "link") {
    shareLink = `${location.origin}${value}`;
  }
}

function setRole(role) {
  canEdit = role !== "view";
  roleText.textContent = ROLE_NAMES[role];
  editTools.hidden = !canEdit;
  sharePanel.hidden = role !== "owner";

  if (!canEdit) {
    finishEditing();
    clearSelection();
    if (deleteMode) {
      stopDeleteMode();
    }
  }

  for (const block of blocks.values()) {
    block.group.draggable(canEdit && !deleteMode);
  }
  stage.size({ width: stageBox.clientWidth, height: stageBox.clientHeight });
}

function showMessage(text, keep = false) {
  toast.textContent = text;
  toast.hidden = false;
  clearTimeout(toastTimer);
  if (!keep) {
    toastTimer = setTimeout(hideMessage, 3000);
  }
}

function hideMessage() {
  toast.hidden = true;
}

function showPeople(text) {
  const people = text ? text.split(",") : [];
  const word = document.createElement("span");
  word.className = "word";
  word.textContent = "Участники: ";
  peopleButton.replaceChildren(word, String(people.length));
  peopleList.innerHTML = "";

  for (const person of people) {
    const [login, role] = person.split(":");
    const item = document.createElement("li");
    const roleText = document.createElement("span");
    item.textContent = `${login} `;
    roleText.textContent = PEOPLE_ROLES[role];
    item.append(roleText);
    peopleList.append(item);
  }
}

function showClosed(reason) {
  closed = true;
  closedText.textContent = reason;
  closedWindow.hidden = false;
}

function clearCanvas() {
  for (const id of [...blocks.keys()]) {
    removeBlock(id);
  }
  for (const id of [...edges.keys()]) {
    removeEdge(id);
  }
}

function makeShape(block) {
  const colors = BLOCK_COLORS[block.type];
  const style = {
    name: "shape",
    stroke: colors.border,
    strokeWidth: 2,
    fillLinearGradientStartPoint: { x: 0, y: 0 },
    fillLinearGradientEndPoint: { x: 0, y: block.h },
    fillLinearGradientColorStops: [0, colors.top, 1, colors.bottom],
    perfectDrawEnabled: false,
  };

  if (block.type === 3) {
    const points = [block.w / 2, 0, block.w, block.h / 2, block.w / 2, block.h, 0, block.h / 2];
    return new Konva.Line({ ...style, points, closed: true });
  }

  if (block.type === 4) {
    const skew = getSkew(block);
    const points = [skew, 0, block.w, 0, block.w - skew, block.h, 0, block.h];
    return new Konva.Line({ ...style, points, closed: true });
  }

  return new Konva.Rect({
    ...style,
    width: block.w,
    height: block.h,
    cornerRadius: block.type === 1 ? block.h / 2 : 6,
  });
}

function getSkew(block) {
  return Math.min(block.w * 0.18, 30);
}

function drawBlock(data) {
  const oldBlock = blocks.get(data.id);
  if (oldBlock) {
    if (oldBlock.group.isDragging() || (editing && editing.id === data.id && editing.kind === "block")) {
      return;
    }
    oldBlock.group.destroy();
  }

  const group = new Konva.Group({ x: data.x, y: data.y, draggable: canEdit && !deleteMode });
  const block = { ...data, group };
  blocks.set(block.id, block);

  group.add(makeShape(block));
  group.add(
    new Konva.Text({
      x: 8,
      y: 4,
      width: block.w - 16,
      height: block.h - 8,
      text: block.text,
      fontSize: 14,
      fill: BLOCK_COLORS[block.type].text,
      fontStyle: "500",
      align: "center",
      verticalAlign: "middle",
      listening: false,
    }),
  );

  group.on("click tap", (event) => {
    event.cancelBubble = true;
    clickBlock(block.id);
  });

  group.on("dblclick dbltap", () => {
    if (canEdit && !deleteMode) {
      startEditing(block.id);
    }
  });

  group.on("dragmove", () => {
    updateEdges(block.id);
    sendPosition(block);
  });

  group.on("dragend", () => {
    saveBlock(block);
  });

  blockLayer.add(group);
  paintBlock(block);
  if (selectedBlock === block.id) {
    addControls(block);
  }
  updateEdges(block.id);
}

function paintBlock(block) {
  const shape = block.group.findOne(".shape");
  if (blocksToDelete.has(block.id)) {
    shape.stroke(RED).strokeWidth(4);
  } else if (selectedBlock === block.id) {
    shape.stroke(ORANGE).strokeWidth(3);
    typeSelect.value = block.type;
  } else {
    shape.stroke(BLOCK_COLORS[block.type].border).strokeWidth(2);
  }
}

function paintEdge(edge) {
  let color = INK;
  if (edgesToDelete.has(edge.id)) {
    color = RED;
  } else if (selectedEdge === edge.id) {
    color = ORANGE;
  }
  edge.arrow.stroke(color).fill(color);
}

function sendPosition(block) {
  const now = performance.now();
  if (now - lastMoveTime > 66) {
    lastMoveTime = now;
    send(`M;${block.id};${Math.round(block.group.x())};${Math.round(block.group.y())}`);
  }
}

function moveBlockSmoothly(id, x, y) {
  const block = blocks.get(id);
  if (block) {
    block.group.to({ x, y, duration: 0.08, onUpdate: () => updateEdges(id) });
  }
}

function saveBlock(block) {
  block.x = Math.round(block.group.x());
  block.y = Math.round(block.group.y());
  send(`F;${block.id};${block.x};${block.y};${block.w};${block.h}`);
}

function addControls(block) {
  const resizer = new Konva.Rect({
    name: "control",
    x: block.w - 8,
    y: block.h - 8,
    width: 16,
    height: 16,
    fill: ORANGE,
    cornerRadius: 3,
    draggable: true,
  });

  resizer.on("dragstart dragmove dragend", (event) => {
    event.cancelBubble = true;
  });

  resizer.on("dragend", () => {
    block.w = Math.max(40, Math.round(resizer.x() + 8));
    block.h = Math.max(30, Math.round(resizer.y() + 8));
    saveBlock(block);
  });

  block.group.add(resizer);

  for (const side of SIDES) {
    const [x, y] = getSidePoint(block, side);
    const dot = new Konva.Circle({
      name: "control",
      x,
      y,
      radius: 7,
      fill: "#fff",
      stroke: ORANGE,
      strokeWidth: 2,
      hitStrokeWidth: 16,
    });

    dot.on("mousedown touchstart", (event) => {
      event.cancelBubble = true;
      startLine(block, side);
    });

    dot.on("click tap", (event) => {
      event.cancelBubble = true;
    });

    block.group.add(dot);
  }
}

function removeControls(block) {
  block.group.find(".control").forEach((control) => control.destroy());
}

function getSidePoint(block, side) {
  const skew = block.type === 4 ? getSkew(block) / 2 : 0;
  const points = [
    [block.w / 2, 0],
    [block.w - skew, block.h / 2],
    [block.w / 2, block.h],
    [skew, block.h / 2],
  ];
  return points[side];
}

function getNearestSide(block, point) {
  let nearest = 0;
  let shortest = Infinity;

  for (const side of SIDES) {
    const [x, y] = getSidePoint(block, side);
    const distance = Math.hypot(block.group.x() + x - point.x, block.group.y() + y - point.y);
    if (distance < shortest) {
      shortest = distance;
      nearest = side;
    }
  }

  return nearest;
}

function findBlockAt(point) {
  const list = [...blocks.values()].reverse();
  return list.find((block) => {
    const x = block.group.x();
    const y = block.group.y();
    const insideX = point.x >= x - 12 && point.x <= x + block.w + 12;
    const insideY = point.y >= y - 12 && point.y <= y + block.h + 12;
    return insideX && insideY;
  });
}

function getPointer(event) {
  stage.setPointersPositions(event);
  return stage.getRelativePointerPosition();
}

function startLine(block, side) {
  const [x, y] = getSidePoint(block, side);
  const startX = block.group.x() + x;
  const startY = block.group.y() + y;

  block.group.draggable(false);
  stage.draggable(false);

  const arrow = new Konva.Arrow({
    points: [startX, startY, startX, startY],
    stroke: ORANGE,
    fill: ORANGE,
    strokeWidth: 2,
    dash: [6, 4],
    pointerLength: 10,
    pointerWidth: 9,
    listening: false,
  });

  edgeLayer.add(arrow);
  newLine = { block, side, arrow, startX, startY };
}

function moveLine(event) {
  if (newLine) {
    const point = getPointer(event);
    newLine.arrow.points([newLine.startX, newLine.startY, point.x, point.y]);
  }
}

function finishLine(event) {
  if (!newLine) {
    if (linkStart) {
      finishLink(event);
    }
    return;
  }

  const { block, side, arrow, startX, startY } = newLine;
  newLine = null;
  arrow.destroy();
  stage.draggable(true);
  blocks.get(block.id)?.group.draggable(true);

  const point = getPointer(event);
  if (Math.hypot(point.x - startX, point.y - startY) < 6) {
    linkStart = { id: block.id, side };
    showMessage("Нажмите на блок, с которым соединить", true);
    return;
  }

  const target = findBlockAt(point);
  if (target && target.id !== block.id) {
    send(`E;${block.id};${side};${target.id};${getNearestSide(target, point)}`);
  }
}

function finishLink(event) {
  if (!stageBox.contains(event.target)) {
    return;
  }

  const point = getPointer(event);
  const target = findBlockAt(point);
  if (target && target.id !== linkStart.id) {
    send(`E;${linkStart.id};${linkStart.side};${target.id};${getNearestSide(target, point)}`);
  }

  linkStart = null;
  hideMessage();
}

function clickBlock(id) {
  if (!canEdit || frameUsed) {
    return;
  }
  if (deleteMode) {
    toggle(blocksToDelete, id);
    paintBlock(blocks.get(id));
    updateDeleteBar();
    return;
  }

  clearSelection();
  selectedBlock = id;
  const block = blocks.get(id);
  paintBlock(block);
  addControls(block);
  typeSelect.hidden = false;
}

function clickEdge(id) {
  if (!canEdit || frameUsed) {
    return;
  }
  if (deleteMode) {
    toggle(edgesToDelete, id);
    paintEdge(edges.get(id));
    updateDeleteBar();
    return;
  }

  clearSelection();
  selectedEdge = id;
  paintEdge(edges.get(id));
}

function toggle(set, id) {
  if (set.has(id)) {
    set.delete(id);
  } else {
    set.add(id);
  }
}

function clearSelection() {
  const block = blocks.get(selectedBlock);
  const edge = edges.get(selectedEdge);
  selectedBlock = null;
  selectedEdge = null;
  typeSelect.hidden = true;

  if (block) {
    paintBlock(block);
    removeControls(block);
  }
  if (edge) {
    paintEdge(edge);
  }
}

function removeBlock(id) {
  const block = blocks.get(id);
  if (block) {
    block.group.destroy();
    blocks.delete(id);
  }

  for (const edge of [...edges.values()]) {
    if (edge.from === id || edge.to === id) {
      removeEdge(edge.id);
    }
  }

  if (selectedBlock === id) {
    selectedBlock = null;
    typeSelect.hidden = true;
  }
  blocksToDelete.delete(id);
  updateDeleteBar();
}

function getEdgePoints(edge) {
  const from = blocks.get(edge.from);
  const to = blocks.get(edge.to);
  if (!from || !to) {
    return null;
  }

  const [startX, startY] = getSidePoint(from, edge.fromSide);
  const [endX, endY] = getSidePoint(to, edge.toSide);
  return [from.group.x() + startX, from.group.y() + startY, to.group.x() + endX, to.group.y() + endY];
}

function getMiddle(points) {
  return { x: (points[0] + points[2]) / 2, y: (points[1] + points[3]) / 2 };
}

function placeLabel(edge, points) {
  const middle = getMiddle(points);
  edge.label.position({ x: middle.x - edge.label.width() / 2, y: middle.y - edge.label.height() / 2 });
  edge.label.visible(edge.text !== "");
}

function drawEdge(edge) {
  const oldEdge = edges.get(edge.id);
  if (oldEdge) {
    oldEdge.text = edge.label;
    oldEdge.label.getText().text(edge.label);
    placeLabel(oldEdge, oldEdge.arrow.points());
    return;
  }

  edge.text = edge.label;
  edge.label = new Konva.Label({ listening: false });
  edge.label.add(new Konva.Tag({ fill: "#fff", stroke: "#dcdcdc", cornerRadius: 6 }));
  edge.label.add(new Konva.Text({ text: edge.text, fontSize: 13, padding: 4, fill: "#1a1a1a" }));

  edge.arrow = new Konva.Arrow({
    points: getEdgePoints(edge) ?? [0, 0, 0, 0],
    stroke: INK,
    fill: INK,
    strokeWidth: 2,
    hitStrokeWidth: 16,
    pointerLength: 10,
    pointerWidth: 9,
  });

  edge.arrow.on("click tap", (event) => {
    event.cancelBubble = true;
    clickEdge(edge.id);
  });

  edge.arrow.on("dblclick dbltap", () => {
    if (canEdit && !deleteMode) {
      startEditingEdge(edge.id);
    }
  });

  edges.set(edge.id, edge);
  edgeLayer.add(edge.arrow, edge.label);
  placeLabel(edge, edge.arrow.points());
}

function removeEdge(id) {
  const edge = edges.get(id);
  if (edge) {
    edge.arrow.destroy();
    edge.label.destroy();
    edges.delete(id);
  }

  if (selectedEdge === id) {
    selectedEdge = null;
  }
  edgesToDelete.delete(id);
  updateDeleteBar();
}

function updateEdges(blockId) {
  for (const edge of edges.values()) {
    if (edge.from === blockId || edge.to === blockId) {
      const points = getEdgePoints(edge);
      if (points) {
        edge.arrow.points(points);
        placeLabel(edge, points);
      }
    }
  }
}

function openEditor(x, y, width, height, value) {
  const box = stageBox.getBoundingClientRect();
  const scale = stage.scaleX();

  editor.value = value;
  editor.hidden = false;
  editor.style.left = `${box.left + stage.x() + x * scale}px`;
  editor.style.top = `${box.top + stage.y() + y * scale}px`;
  editor.style.width = `${width * scale}px`;
  editor.style.height = `${height * scale}px`;
  editor.focus();
}

function startEditing(id) {
  const block = blocks.get(id);
  editing = { kind: "block", id };
  editor.maxLength = 1000;
  openEditor(block.group.x(), block.group.y(), block.w, block.h, block.text);
}

function startEditingEdge(id) {
  const edge = edges.get(id);
  const middle = getMiddle(edge.arrow.points());
  editing = { kind: "edge", id };
  editor.maxLength = 200;
  openEditor(middle.x - 80, middle.y - 18, 160, 36, edge.text);
}

function finishEditing() {
  if (editing === null) {
    return;
  }

  const { kind, id } = editing;
  editing = null;
  editor.hidden = true;
  const text = editor.value.replace(/\n/g, " ");
  send(kind === "block" ? `T;${id};${text}` : `G;${id};${text}`);
}

function undo() {
  if (canEdit && !deleteMode) {
    send("Z");
  }
}

function getBounds() {
  const list = [...blocks.values()];
  const left = Math.min(...list.map((block) => block.group.x()));
  const top = Math.min(...list.map((block) => block.group.y()));
  const right = Math.max(...list.map((block) => block.group.x() + block.w));
  const bottom = Math.max(...list.map((block) => block.group.y() + block.h));
  return { x: left, y: top, width: right - left, height: bottom - top };
}

function makePicture() {
  clearSelection();
  const padding = 30;
  const bounds = getBounds();
  const oldScale = stage.scaleX();
  const oldPosition = stage.position();

  stage.scale({ x: 1, y: 1 });
  stage.position({ x: padding - bounds.x, y: padding - bounds.y });
  const picture = stage.toCanvas({
    x: 0,
    y: 0,
    width: bounds.width + padding * 2,
    height: bounds.height + padding * 2,
    pixelRatio: 2,
  });
  stage.scale({ x: oldScale, y: oldScale });
  stage.position(oldPosition);

  const result = document.createElement("canvas");
  result.width = picture.width;
  result.height = picture.height;
  const context = result.getContext("2d");
  context.fillStyle = "#fff";
  context.fillRect(0, 0, result.width, result.height);
  context.drawImage(picture, 0, 0);
  return result;
}

function getFileName() {
  const name = titleText.textContent.replace(/[\\/:*?"<>|]/g, "_").trim();
  return name || "схема";
}

function exportPng() {
  if (blocks.size === 0) {
    showMessage("Холст пустой");
    return;
  }

  const link = document.createElement("a");
  link.download = `${getFileName()}.png`;
  link.href = makePicture().toDataURL("image/png");
  link.click();
}

function exportPdf() {
  if (blocks.size === 0) {
    showMessage("Холст пустой");
    return;
  }

  const picture = makePicture();
  const width = picture.width / 2;
  const height = picture.height / 2;
  const pdf = new jspdf.jsPDF({
    orientation: width > height ? "landscape" : "portrait",
    unit: "px",
    format: [width, height],
  });
  pdf.addImage(picture.toDataURL("image/png"), "PNG", 0, 0, width, height);
  pdf.save(`${getFileName()}.pdf`);
}

function startDeleteMode() {
  if (deleteMode || !canEdit) {
    return;
  }

  clearSelection();
  deleteMode = true;
  deleteBar.hidden = false;
  stage.draggable(false);
  stage.size({ width: stageBox.clientWidth, height: stageBox.clientHeight });

  for (const block of blocks.values()) {
    block.group.draggable(false);
  }
  updateDeleteBar();
}

function stopDeleteMode() {
  deleteMode = false;
  stage.draggable(true);
  frame?.rect.destroy();
  frame = null;
  blocksToDelete.clear();
  edgesToDelete.clear();
  deleteBar.hidden = true;
  confirmWindow.hidden = true;
  stage.size({ width: stageBox.clientWidth, height: stageBox.clientHeight });

  for (const block of blocks.values()) {
    block.group.draggable(canEdit);
    paintBlock(block);
  }
  for (const edge of edges.values()) {
    paintEdge(edge);
  }
}

function updateDeleteBar() {
  const total = blocksToDelete.size + edgesToDelete.size;
  deleteInfo.textContent = `Нажмите или обведите рамкой то, что удалить. Выбрано: ${total}`;
  deleteNext.disabled = total === 0;
}

function startFrame() {
  if (!deleteMode) {
    return;
  }

  frameUsed = false;
  const point = stage.getRelativePointerPosition();
  const rect = new Konva.Rect({
    x: point.x,
    y: point.y,
    width: 0,
    height: 0,
    stroke: RED,
    strokeWidth: 1,
    dash: [6, 4],
    fill: "rgba(192, 53, 43, 0.08)",
    listening: false,
  });

  frameLayer.add(rect);
  frame = { rect, startX: point.x, startY: point.y };
}

function moveFrame() {
  if (!frame) {
    return;
  }

  const point = stage.getRelativePointerPosition();
  frame.rect.position({ x: Math.min(frame.startX, point.x), y: Math.min(frame.startY, point.y) });
  frame.rect.size({ width: Math.abs(point.x - frame.startX), height: Math.abs(point.y - frame.startY) });
}

function isInside(area, x, y) {
  return x >= area.x && x <= area.x + area.width && y >= area.y && y <= area.y + area.height;
}

function touchesArea(block, area) {
  const x = block.group.x();
  const y = block.group.y();
  return x < area.x + area.width && x + block.w > area.x && y < area.y + area.height && y + block.h > area.y;
}

function finishFrame() {
  if (!frame) {
    return;
  }

  const area = {
    x: frame.rect.x(),
    y: frame.rect.y(),
    width: frame.rect.width(),
    height: frame.rect.height(),
  };
  frame.rect.destroy();
  frame = null;

  if (area.width < 6 && area.height < 6) {
    return;
  }
  frameUsed = true;
  setTimeout(() => {
    frameUsed = false;
  }, 0);

  const blockIds = [...blocks.values()].filter((block) => touchesArea(block, area)).map((block) => block.id);
  const edgeIds = [...edges.values()]
    .filter((edge) => {
      const points = getEdgePoints(edge);
      if (!points) {
        return false;
      }
      const middle = getMiddle(points);
      return isInside(area, middle.x, middle.y);
    })
    .map((edge) => edge.id);

  const allSelected =
    blockIds.length + edgeIds.length > 0 &&
    blockIds.every((id) => blocksToDelete.has(id)) &&
    edgeIds.every((id) => edgesToDelete.has(id));

  for (const id of blockIds) {
    if (allSelected) {
      blocksToDelete.delete(id);
    } else {
      blocksToDelete.add(id);
    }
    paintBlock(blocks.get(id));
  }

  for (const id of edgeIds) {
    if (allSelected) {
      edgesToDelete.delete(id);
    } else {
      edgesToDelete.add(id);
    }
    paintEdge(edges.get(id));
  }

  updateDeleteBar();
}

function askConfirmation() {
  let text = `Удалить блоков: ${blocksToDelete.size}, связей: ${edgesToDelete.size}?`;
  if (blocksToDelete.size > 0) {
    text += " Связи этих блоков тоже удалятся.";
  }
  confirmText.textContent = text;
  confirmWindow.hidden = false;
}

function deleteSelected() {
  const blockIds = [...blocksToDelete].join(",");
  const edgeIds = [...edgesToDelete].join(",");
  send(`K;${blockIds};${edgeIds}`);
  stopDeleteMode();
}

function showZoom() {
  zoomValue.textContent = `${Math.round(stage.scaleX() * 100)}%`;
}

function fitAll() {
  if (blocks.size === 0) {
    return;
  }

  const bounds = getBounds();
  const scale = Math.min(
    2,
    Math.max(0.2, Math.min((stage.width() - 80) / bounds.width, (stage.height() - 80) / bounds.height)),
  );
  stage.scale({ x: scale, y: scale });
  stage.position({
    x: (stage.width() - bounds.width * scale) / 2 - bounds.x * scale,
    y: (stage.height() - bounds.height * scale) / 2 - bounds.y * scale,
  });
  showZoom();
}

function closePanels() {
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.hidden = true;
  });
}

function zoom(factor, x, y) {
  const oldScale = stage.scaleX();
  const newScale = Math.min(4, Math.max(0.2, oldScale * factor));
  const pointX = (x - stage.x()) / oldScale;
  const pointY = (y - stage.y()) / oldScale;

  stage.scale({ x: newScale, y: newScale });
  stage.position({ x: x - pointX * newScale, y: y - pointY * newScale });
  showZoom();
}

function addBlock(type) {
  if (!canEdit) {
    return;
  }
  const scale = stage.scaleX();
  const centerX = (stage.width() / 2 - stage.x()) / scale;
  const centerY = (stage.height() / 2 - stage.y()) / scale;
  const shift = Math.random() * 40 - 20;
  const x = Math.round(centerX - 80 + shift);
  const y = Math.round(centerY - 40 + shift);
  send(`A;${type};${x};${y};160;80;${BLOCK_NAMES[type]}`);
}

document.querySelectorAll("[data-type]").forEach((button) => {
  button.addEventListener("click", () => addBlock(button.dataset.type));
});

document.getElementById("delete").addEventListener("click", startDeleteMode);
document.getElementById("undo").addEventListener("click", undo);
document.getElementById("fit").addEventListener("click", fitAll);

document.getElementById("export-png").addEventListener("click", () => {
  closePanels();
  exportPng();
});

document.getElementById("export-pdf").addEventListener("click", () => {
  closePanels();
  exportPdf();
});

document.querySelectorAll("[data-panel]").forEach((button) => {
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    const panel = document.getElementById(button.dataset.panel);
    const wasHidden = panel.hidden;
    closePanels();
    panel.hidden = !wasHidden;
  });
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".menu")) {
    closePanels();
  }
});

typeSelect.addEventListener("change", () => {
  if (selectedBlock !== null) {
    send(`Y;${selectedBlock};${typeSelect.value}`);
  }
});


document.getElementById("delete-cancel").addEventListener("click", stopDeleteMode);
document.getElementById("confirm-yes").addEventListener("click", deleteSelected);
deleteNext.addEventListener("click", askConfirmation);

document.getElementById("confirm-no").addEventListener("click", () => {
  confirmWindow.hidden = true;
});

accessSelect.addEventListener("change", async () => {
  await fetch(`/api/canvases/${canvasId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access: Number(accessSelect.value) }),
  });
});

document.getElementById("copy").addEventListener("click", async () => {
  closePanels();
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(shareLink);
    showMessage("Ссылка скопирована");
  } else {
    prompt("Скопируйте ссылку", shareLink);
  }
});

document.getElementById("zoom-in").addEventListener("click", () => {
  zoom(1.2, stage.width() / 2, stage.height() / 2);
});

document.getElementById("zoom-out").addEventListener("click", () => {
  zoom(1 / 1.2, stage.width() / 2, stage.height() / 2);
});

stage.on("click tap", (event) => {
  if (event.target === stage) {
    clearSelection();
  }
});

stage.on("mousedown touchstart", startFrame);
stage.on("mousemove touchmove", moveFrame);
stage.on("mouseup touchend", finishFrame);

stage.on("wheel", (event) => {
  event.evt.preventDefault();
  const pointer = stage.getPointerPosition();
  zoom(event.evt.deltaY < 0 ? 1.1 : 1 / 1.1, pointer.x, pointer.y);
});

editor.addEventListener("blur", finishEditing);

editor.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    finishEditing();
  }
});

window.addEventListener("keydown", (event) => {
  if (event.target === editor) {
    return;
  }
  if (event.key === "Delete") {
    startDeleteMode();
  }
  if (event.key === "Escape" && deleteMode) {
    stopDeleteMode();
  }
  if ((event.ctrlKey || event.metaKey) && event.code === "KeyZ") {
    event.preventDefault();
    undo();
  }
});

window.addEventListener("pointermove", moveLine);
window.addEventListener("pointerup", finishLine);
window.addEventListener("pointerup", finishFrame);

window.addEventListener("resize", () => {
  stage.size({ width: stageBox.clientWidth, height: stageBox.clientHeight });
});

connect();
