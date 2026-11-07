const BLOCK_NAMES = {
  1: "Начало/конец",
  2: "Процесс",
  3: "Решение",
  4: "Данные",
};

const GRAY = "#47566a";
const BLUE = "#2f6fde";
const RED = "#c0352b";
const SIDES = [0, 1, 2, 3];

const stageBox = document.getElementById("stage");
const statusText = document.getElementById("status");
const editor = document.getElementById("editor");
const deleteBar = document.getElementById("delete-bar");
const deleteInfo = document.getElementById("delete-info");
const deleteNext = document.getElementById("delete-next");
const confirmWindow = document.getElementById("confirm");
const confirmText = document.getElementById("confirm-text");

const stage = new Konva.Stage({
  container: "stage",
  width: stageBox.clientWidth,
  height: stageBox.clientHeight,
  draggable: true,
});

const edgeLayer = new Konva.Layer();
const blockLayer = new Konva.Layer();
stage.add(edgeLayer, blockLayer);

const blocks = new Map();
const edges = new Map();
const blocksToDelete = new Set();
const edgesToDelete = new Set();

let socket = null;
let selectedBlock = null;
let selectedEdge = null;
let editingBlock = null;
let deleteMode = false;
let newLine = null;
let linkStart = null;
let lastMoveTime = 0;

function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(message);
  }
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${location.host}/ws`);

  socket.onopen = () => {
    clearCanvas();
    statusText.textContent = "Подключено";
  };

  socket.onmessage = (event) => {
    handleMessage(event.data);
  };

  socket.onclose = () => {
    statusText.textContent = "Нет связи, переподключаемся…";
    setTimeout(connect, 2000);
  };
}

function handleMessage(message) {
  const parts = message.split(";");
  const command = parts[0];

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
    });
  }

  if (command === "D") {
    removeEdge(Number(parts[1]));
  }
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
  const style = { fill: "#fff", stroke: GRAY, strokeWidth: 2, name: "shape" };

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
    if (oldBlock.group.isDragging() || editingBlock === data.id) {
      return;
    }
    oldBlock.group.destroy();
  }

  const group = new Konva.Group({ x: data.x, y: data.y, draggable: !deleteMode });
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
      fill: "#1c2430",
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
    if (!deleteMode) {
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
    shape.stroke(BLUE).strokeWidth(2);
  } else {
    shape.stroke(GRAY).strokeWidth(2);
  }
}

function paintEdge(edge) {
  let color = GRAY;
  if (edgesToDelete.has(edge.id)) {
    color = RED;
  } else if (selectedEdge === edge.id) {
    color = BLUE;
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
    fill: BLUE,
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
      stroke: BLUE,
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
    stroke: BLUE,
    fill: BLUE,
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
    statusText.textContent = "Нажмите на блок, с которым соединить";
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
  statusText.textContent = "Подключено";
}

function clickBlock(id) {
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
}

function clickEdge(id) {
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

function drawEdge(edge) {
  edge.arrow = new Konva.Arrow({
    points: getEdgePoints(edge) ?? [0, 0, 0, 0],
    stroke: GRAY,
    fill: GRAY,
    strokeWidth: 2,
    hitStrokeWidth: 16,
    pointerLength: 10,
    pointerWidth: 9,
  });

  edge.arrow.on("click tap", (event) => {
    event.cancelBubble = true;
    clickEdge(edge.id);
  });

  edges.set(edge.id, edge);
  edgeLayer.add(edge.arrow);
}

function removeEdge(id) {
  const edge = edges.get(id);
  if (edge) {
    edge.arrow.destroy();
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
      }
    }
  }
}

function startEditing(id) {
  const block = blocks.get(id);
  const box = stageBox.getBoundingClientRect();
  const scale = stage.scaleX();

  editingBlock = id;
  editor.value = block.text;
  editor.hidden = false;
  editor.style.left = `${box.left + stage.x() + block.group.x() * scale}px`;
  editor.style.top = `${box.top + stage.y() + block.group.y() * scale}px`;
  editor.style.width = `${block.w * scale}px`;
  editor.style.height = `${block.h * scale}px`;
  editor.focus();
}

function finishEditing() {
  if (editingBlock === null) {
    return;
  }

  const id = editingBlock;
  editingBlock = null;
  editor.hidden = true;
  send(`T;${id};${editor.value.replace(/\n/g, " ")}`);
}

function startDeleteMode() {
  if (deleteMode) {
    return;
  }

  clearSelection();
  deleteMode = true;
  deleteBar.hidden = false;
  stage.size({ width: stageBox.clientWidth, height: stageBox.clientHeight });

  for (const block of blocks.values()) {
    block.group.draggable(false);
  }
  updateDeleteBar();
}

function stopDeleteMode() {
  deleteMode = false;
  blocksToDelete.clear();
  edgesToDelete.clear();
  deleteBar.hidden = true;
  confirmWindow.hidden = true;
  stage.size({ width: stageBox.clientWidth, height: stageBox.clientHeight });

  for (const block of blocks.values()) {
    block.group.draggable(true);
    paintBlock(block);
  }
  for (const edge of edges.values()) {
    paintEdge(edge);
  }
}

function updateDeleteBar() {
  const total = blocksToDelete.size + edgesToDelete.size;
  deleteInfo.textContent = `Выберите, что удалить. Выбрано: ${total}`;
  deleteNext.disabled = total === 0;
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
  for (const id of edgesToDelete) {
    send(`D;${id}`);
  }
  for (const id of blocksToDelete) {
    send(`X;${id}`);
  }
  stopDeleteMode();
}

function zoom(factor, x, y) {
  const oldScale = stage.scaleX();
  const newScale = Math.min(4, Math.max(0.2, oldScale * factor));
  const pointX = (x - stage.x()) / oldScale;
  const pointY = (y - stage.y()) / oldScale;

  stage.scale({ x: newScale, y: newScale });
  stage.position({ x: x - pointX * newScale, y: y - pointY * newScale });
}

function addBlock(type) {
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
document.getElementById("delete-cancel").addEventListener("click", stopDeleteMode);
document.getElementById("confirm-yes").addEventListener("click", deleteSelected);
deleteNext.addEventListener("click", askConfirmation);

document.getElementById("confirm-no").addEventListener("click", () => {
  confirmWindow.hidden = true;
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
});

window.addEventListener("pointermove", moveLine);
window.addEventListener("pointerup", finishLine);

window.addEventListener("resize", () => {
  stage.size({ width: stageBox.clientWidth, height: stageBox.clientHeight });
});

connect();
