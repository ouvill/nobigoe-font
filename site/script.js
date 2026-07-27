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
  "ー": { prefix: "ねえ", code: "U+30FC" },
  "〜": { prefix: "ざわ", code: "U+301C" },
  "〰": { prefix: "ざわ", code: "U+3030" },
  "―": { prefix: "しん", code: "U+2015" },
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

function updateTesterSize() {
  const size = `${sizeInput.value}px`;
  sizeValue.value = size;
  testerText.style.fontSize = size;
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

for (const button of sampleButtons) {
  button.addEventListener("click", () => {
    testerText.textContent = button.dataset.sample.replaceAll("\\n", "\n");
    testerText.focus();
  });
}

async function revealFont() {
  try {
    await document.fonts.load("64px Choon", "ー〜〰あ゙！！？？");
    await document.fonts.ready;
  } finally {
    root.classList.remove("fonts-loading");
    root.classList.add("fonts-ready");
  }
}

updateExtension();
updateTesterSize();
revealFont();
