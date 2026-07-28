const siteIdentity = Object.freeze({
  nameJa: "のびごえ明朝",
  nameEn: "Nobigoe Mincho",
  releaseUrl: "https://github.com/ouvill/nobigoe-font/releases",
});

for (const element of document.querySelectorAll("[data-project-name]")) {
  element.textContent = siteIdentity.nameJa;
}
for (const element of document.querySelectorAll("[data-project-name-en]")) {
  element.textContent = siteIdentity.nameEn;
}
for (const link of document.querySelectorAll("[data-release-url]")) {
  link.href = siteIdentity.releaseUrl;
}
const brandLink = document.querySelector(".brand");
brandLink.setAttribute("aria-label", `${siteIdentity.nameJa} トップへ`);

const root = document.documentElement;
root.classList.add("fonts-loading");

const symbolButtons = [...document.querySelectorAll("[data-symbol]")];
const repeatInput = document.querySelector("#repeat-count");
const repeatValue = document.querySelector("#repeat-value");
const extensionOutput = document.querySelector("#extension-output");
const extensionStage = document.querySelector("#extension-stage");
const extensionCode = document.querySelector("#extension-code");
const extensionMode = document.querySelector("#extension-mode");

const symbolDetails = {
  "ー": { prefix: "余韻", code: "U+30FC" },
  "〜": { prefix: "水面", code: "U+301C" },
  "〰": { prefix: "波紋", code: "U+3030" },
  "―": { prefix: "静寂", code: "U+2015" },
};

let selectedSymbol = "ー";
let updateFrame = 0;

function fitExtension() {
  const glyphCount = [...extensionOutput.textContent].length;
  const vertical = extensionStage.classList.contains("is-vertical");
  if (vertical) {
    const available = Math.min(500, extensionStage.clientHeight - 90);
    const size = Math.max(24, Math.min(70, available / glyphCount));
    extensionOutput.style.fontSize = `${size}px`;
    return;
  }
  if (window.matchMedia("(max-width: 740px)").matches) {
    const available = extensionStage.clientWidth - 48;
    const size = Math.max(22, Math.min(44, available / glyphCount));
    extensionOutput.style.fontSize = `${size}px`;
    return;
  }
  extensionOutput.style.removeProperty("font-size");
}

function updateExtension() {
  cancelAnimationFrame(updateFrame);
  extensionOutput.classList.add("is-updating");
  updateFrame = requestAnimationFrame(() => {
    const count = Number(repeatInput.value);
    const detail = symbolDetails[selectedSymbol];
    repeatValue.value = String(count);
    extensionOutput.textContent = detail.prefix + selectedSymbol.repeat(count);
    extensionCode.textContent = detail.code;
    fitExtension();
    extensionOutput.classList.remove("is-updating");
  });
}

for (const button of symbolButtons) {
  button.addEventListener("click", () => {
    selectedSymbol = button.dataset.symbol;
    for (const candidate of symbolButtons) {
      const active = candidate === button;
      candidate.classList.toggle("is-active", active);
      candidate.setAttribute("aria-pressed", String(active));
    }
    updateExtension();
  });
}

repeatInput.addEventListener("input", updateExtension);
window.addEventListener("resize", fitExtension);

extensionMode.addEventListener("click", () => {
  const vertical = !extensionStage.classList.contains("is-vertical");
  extensionStage.classList.toggle("is-vertical", vertical);
  extensionMode.setAttribute("aria-pressed", String(vertical));
  extensionMode.textContent = vertical ? "横組に戻す" : "縦組にする";
  fitExtension();
});

const sizeInput = document.querySelector("#font-size");
const sizeValue = document.querySelector("#font-size-value");
const testerText = document.querySelector("#tester-text");
const testerCanvas = document.querySelector("#tester-canvas");
const writingModeButtons = [...document.querySelectorAll("[data-writing-mode]")];
const sampleButtons = [...document.querySelectorAll("[data-sample]")];
const punctuationStyleButtons = [
  ...document.querySelectorAll("[data-punctuation-style]"),
];
const rubyModeButtons = [...document.querySelectorAll("[data-ruby-mode]")];
let punctuationStyle = "";
let rubyMode = false;

function updateTesterSize() {
  const size = `${sizeInput.value}px`;
  sizeValue.value = size;
  testerText.style.fontSize = size;
}

function updateTesterFeatures() {
  const features = [];
  if (punctuationStyle) {
    features.push(`"${punctuationStyle}" 1`);
  }
  if (rubyMode) {
    features.push('"ruby" 1');
  }
  testerText.style.fontFeatureSettings = features.join(", ") || "normal";
}

sizeInput.addEventListener("input", updateTesterSize);

for (const button of writingModeButtons) {
  button.addEventListener("click", () => {
    const vertical = button.dataset.writingMode === "vertical";
    testerCanvas.classList.toggle("is-vertical", vertical);
    for (const candidate of writingModeButtons) {
      const active = candidate === button;
      candidate.classList.toggle("is-active", active);
      candidate.setAttribute("aria-pressed", String(active));
    }
  });
}

for (const button of punctuationStyleButtons) {
  button.addEventListener("click", () => {
    punctuationStyle = button.dataset.punctuationStyle;
    updatePressedButtons(punctuationStyleButtons, button);
    updateTesterFeatures();
  });
}

for (const button of rubyModeButtons) {
  button.addEventListener("click", () => {
    rubyMode = button.dataset.rubyMode === "ruby";
    updatePressedButtons(rubyModeButtons, button);
    updateTesterFeatures();
  });
}

for (const button of sampleButtons) {
  button.addEventListener("click", () => {
    testerText.textContent = button.dataset.sample.replaceAll("\\n", "\n");
    testerText.focus();
  });
}

const catalogGrid = document.querySelector("#catalog-grid");
const catalogCount = document.querySelector("#catalog-count");
const catalogWritingMode = document.querySelector("#catalog-writing-mode");
const markTypeButtons = [...document.querySelectorAll("[data-mark-type]")];
const markScriptButtons = [...document.querySelectorAll("[data-mark-script]")];
const catalogFamilyButtons = [
  ...document.querySelectorAll("[data-catalog-family]"),
];
const catalogWeightButtons = [
  ...document.querySelectorAll("[data-catalog-weight]"),
];
const catalogFontStatus = document.querySelector("#catalog-font-status");

const catalogWeightNames = {
  200: "ExtraLight",
  300: "Light",
  400: "Regular",
  500: "Medium",
  600: "SemiBold",
  700: "Bold",
  900: "Black",
};

let catalogData = [];
let activeMarkType = "all";
let activeMarkScript = "all";
let activeCatalogFamily = "noto";
let activeNotoWeight = 400;

function updatePressedButtons(buttons, activeButton) {
  for (const button of buttons) {
    const active = button === activeButton;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  }
}

function updateCatalogTypeface() {
  const koburi = activeCatalogFamily === "koburi";
  const weight = koburi ? 400 : activeNotoWeight;
  const family = koburi ? "Nobigoe Koburi Demo" : "Nobigoe Weight";
  const label = koburi
    ? "のびごえこぶり明朝 Regular 400"
    : `のびごえ明朝 ${catalogWeightNames[weight]} ${weight}`;

  catalogGrid.dataset.catalogFamily = activeCatalogFamily;
  catalogGrid.style.setProperty("--catalog-font-weight", String(weight));
  catalogFontStatus.textContent = label;
  catalogGrid.setAttribute(
    "aria-label",
    `${label}の濁点・半濁点付き仮名と記号一覧`,
  );

  for (const button of catalogFamilyButtons) {
    const active = button.dataset.catalogFamily === activeCatalogFamily;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  }
  for (const button of catalogWeightButtons) {
    const buttonWeight = Number(button.dataset.catalogWeight);
    const active = buttonWeight === weight;
    button.disabled = koburi && buttonWeight !== 400;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  }

  document.fonts
    .load(`${weight} 58px "${family}"`, "あ゙か゚ア゙カ゚")
    .catch((error) => console.error(error));
}

function createCatalogBadge(text, label) {
  const badge = document.createElement("span");
  badge.className = "catalog-badge";
  badge.textContent = text;
  badge.title = label;
  return badge;
}

function createCatalogItem(mark) {
  const item = document.createElement("article");
  item.className = "catalog-item";
  item.setAttribute("role", "listitem");
  item.setAttribute(
    "aria-label",
    `${mark.glyph}、${mark.codepoints}${mark.koburiPua ? `、源暎こぶり明朝外字 ${mark.koburiPua}` : ""}`,
  );

  const glyph = document.createElement("span");
  glyph.className = "catalog-glyph";
  glyph.textContent = mark.glyph;

  const meta = document.createElement("span");
  meta.className = "catalog-item-meta";
  const base = document.createElement("span");
  base.textContent = `${mark.base} + ${mark.mark}`;
  const codepoints = document.createElement("span");
  codepoints.textContent = mark.koburiPua
    ? `${mark.codepoints} / 外字 ${mark.koburiPua}`
    : mark.codepoints;
  meta.append(base, codepoints);

  const badges = document.createElement("span");
  badges.className = "catalog-badges";
  if (mark.koburiPua) {
    badges.append(createCatalogBadge("外", `源暎こぶり明朝外字 ${mark.koburiPua}`));
  }
  if (mark.small) {
    badges.append(createCatalogBadge("小", "小書き仮名"));
  }
  if (mark.vertical) {
    badges.append(createCatalogBadge("縦", "Adobe-Manga1-0参照の縦組専用字形"));
  }

  item.append(glyph, meta, badges);
  return item;
}

function renderCatalog() {
  const visible = catalogData.filter((mark) => {
    const matchesType =
      activeMarkType === "all" || mark.type === activeMarkType;
    const matchesScript =
      activeMarkScript === "all" || mark.script === activeMarkScript;
    return matchesType && matchesScript;
  });
  const fragment = document.createDocumentFragment();
  for (const mark of visible) {
    fragment.append(createCatalogItem(mark));
  }
  catalogGrid.replaceChildren(fragment);
  catalogCount.textContent = String(visible.length);
}

for (const button of markTypeButtons) {
  button.addEventListener("click", () => {
    activeMarkType = button.dataset.markType;
    updatePressedButtons(markTypeButtons, button);
    renderCatalog();
  });
}

for (const button of markScriptButtons) {
  button.addEventListener("click", () => {
    activeMarkScript = button.dataset.markScript;
    updatePressedButtons(markScriptButtons, button);
    renderCatalog();
  });
}

for (const button of catalogFamilyButtons) {
  button.addEventListener("click", () => {
    activeCatalogFamily = button.dataset.catalogFamily;
    updateCatalogTypeface();
  });
}

for (const button of catalogWeightButtons) {
  button.addEventListener("click", () => {
    activeNotoWeight = Number(button.dataset.catalogWeight);
    updateCatalogTypeface();
  });
}

catalogWritingMode.addEventListener("click", () => {
  const vertical = !catalogGrid.classList.contains("is-vertical");
  catalogGrid.classList.toggle("is-vertical", vertical);
  catalogWritingMode.setAttribute("aria-pressed", String(vertical));
  catalogWritingMode.textContent = vertical
    ? "横組で見る"
    : "縦組で見る";
});

async function loadCatalog() {
  try {
    const response = await fetch("marks-data.json?v=1.024");
    if (!response.ok) {
      throw new Error(`Glyph catalog: HTTP ${response.status}`);
    }
    catalogData = await response.json();
    renderCatalog();
  } catch (error) {
    catalogCount.textContent = "0";
    catalogGrid.textContent = "字形データを読み込めませんでした。";
    console.error(error);
  }
}

async function revealFont() {
  try {
    await Promise.all([
      document.fonts.load("64px Nobigoe", "ー〜〰あ゙♡゙♥゙！！？？"),
      document.fonts.load('500 48px "Nobigoe Weight"', "声を、どこまでも。"),
      document.fonts.load('48px "Nobigoe Koburi Demo"', "あのねーーーー"),
    ]);
    await document.fonts.ready;
  } finally {
    root.classList.remove("fonts-loading");
    root.classList.add("fonts-ready");
  }
}

updateExtension();
updateTesterSize();
updateCatalogTypeface();
loadCatalog();
revealFont();
