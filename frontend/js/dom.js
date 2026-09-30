// Минимальный помощник для сборки DOM. Весь текст вставляется как текстовые узлы,
// поэтому данные из API не могут внедрить разметку.

export function h(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs ?? {})) {
    if (value == null || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") {
      element.addEventListener(key.slice(2), value);
    } else if (key === "class") {
      element.className = value;
    } else if (value === true) {
      element.setAttribute(key, "");
    } else {
      element.setAttribute(key, value);
    }
  }
  element.append(...toNodes(children));
  return element;
}

function toNodes(children) {
  return children
    .flat(Infinity)
    .filter((child) => child != null && child !== false)
    .map((child) => (child.nodeType ? child : document.createTextNode(String(child))));
}

export function replaceContent(element, ...children) {
  element.replaceChildren(...toNodes(children));
}

const SVG_NS = "http://www.w3.org/2000/svg";

export function bookmarkIcon(filled) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "20");
  svg.setAttribute("height", "20");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", "M6.5 3.5h11v17l-5.5-4-5.5 4z");
  path.setAttribute("fill", filled ? "currentColor" : "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.8");
  path.setAttribute("stroke-linejoin", "round");
  svg.append(path);
  return svg;
}
