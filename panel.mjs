function pick(style, scheme, key) {
  return scheme[key] ?? style[key];
}

export function resolvePanel(style, scheme) {
  const corner = pick(style, scheme, "corner_radius") ?? 0;
  const borderWidth = pick(style, scheme, "border_width") ?? 0;
  const borderHeight = pick(style, scheme, "border_height") ?? 0;
  const vertical = pick(style, scheme, "text_orientation") === "vertical";
  const along = borderWidth + corner;
  const across = borderHeight + corner;
  return {
    fontFace: pick(style, scheme, "font_face"),
    cornerRadius: corner,
    hilitedCornerRadius: pick(style, scheme, "hilited_corner_radius") ?? 0,
    fontPoint: pick(style, scheme, "font_point") ?? 16,
    labelFontPoint: pick(style, scheme, "label_font_point") ?? pick(style, scheme, "font_point") ?? 16,
    edgeInset: vertical
      ? { width: across, height: along }
      : { width: along, height: across },
    preedit: pick(style, scheme, "inline_preedit") === true ? null : undefined,
    highlightShadow: pick(style, scheme, "shadow_size") ?? 0,
    panelShadow: 0,
    layout: pick(style, scheme, "candidate_list_layout") ?? "stacked",
    lineSpacing: pick(style, scheme, "line_spacing") ?? 0,
  };
}

function yamlScalar(value) {
  if (/^[A-Za-z0-9_./+-]+$/.test(value)) return value;
  return `"${value.replaceAll("\\", "\\\\").replaceAll("\"", "\\\"")}"`;
}

function replaceStyle(yaml, key, value) {
  return yaml.replace(new RegExp(`^(  style/${key}:\\s*).*$`, "m"), `$1${yamlScalar(value)}`);
}
function replaceInScheme(yaml, scheme, key, value) {
  const header = new RegExp(`^    ${scheme}:\\s*$`, "m").exec(yaml);
  if (!header) return yaml;
  const afterHeader = header.index + header[0].length;
  const boundary = yaml.slice(afterHeader).search(/\n    [A-Za-z0-9_]+:|\n  [A-Za-z_#]/);
  const end = boundary < 0 ? yaml.length : afterHeader + boundary;
  const block = yaml.slice(header.index, end);
  const line = new RegExp(`^(      ${key}:\\s*)(.*)$`, "m");
  if (!line.test(block)) return yaml;
  const updated = block.replace(line, (_all, prefix, raw) => {
    const hash = raw.indexOf(" #");
    const comment = hash >= 0 ? raw.slice(hash) : "";
    return `${prefix}${yamlScalar(value)}${comment}`;
  });
  return yaml.slice(0, header.index) + updated + yaml.slice(end);
}

export function applyPatch(yaml, selection) {
  let next = yaml;
  next = replaceStyle(next, "color_scheme", selection.scheme);
  next = replaceStyle(next, "color_scheme_dark", selection.scheme);
  next = replaceStyle(next, "candidate_list_layout", selection.layout);
  next = replaceStyle(next, "font_face", selection.font);
  next = replaceStyle(next, "label_font_face", selection.font);
  next = replaceInScheme(next, selection.scheme, "font_face", selection.font);
  next = replaceInScheme(next, selection.scheme, "label_font_face", selection.font);
  next = replaceInScheme(next, selection.scheme, "candidate_list_layout", selection.layout);
  for (const key of ["inline_preedit", "font_point", "label_font_point"]) {
    if (!selection.style || selection.style[key] === undefined) continue;
    next = replaceStyle(next, key, String(selection.style[key]));
    next = replaceInScheme(next, selection.scheme, key, String(selection.style[key]));
  }
  return next;
}

const STYLE_KEYS = [
  "font_face",
  "corner_radius",
  "border_height",
  "border_width",
  "text_orientation",
  "inline_preedit",
  "shadow_size",
  "candidate_list_layout",
  "line_spacing",
  "hilited_corner_radius",
  "font_point",
  "label_font_point",
  "color_scheme",
];

function parseScalar(raw) {
  let text = raw.trim();
  const hash = text.indexOf(" #");
  if (hash >= 0) text = text.slice(0, hash).trim();
  if (text.startsWith("\"") && text.endsWith("\"") && text.length >= 2) {
    return text.slice(1, -1).replaceAll("\\\"", "\"").replaceAll("\\\\", "\\");
  }
  if (text === "true") return true;
  if (text === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(text)) return Number(text);
  return text;
}

export function previewInput(yaml, schemeId) {
  const style = {};
  for (const key of STYLE_KEYS) {
    const match = yaml.match(new RegExp(`^  style/${key}:\\s*(.*)$`, "m"));
    if (match) style[key] = parseScalar(match[1]);
  }
  const scheme = {};
  const header = new RegExp(`^    ${schemeId}:\\s*$`, "m").exec(yaml);
  if (header) {
    const after = header.index + header[0].length;
    const boundary = yaml.slice(after).search(/\n    [A-Za-z0-9_]+:|\n  [A-Za-z_#]/);
    const end = boundary < 0 ? yaml.length : after + boundary;
    for (const line of yaml.slice(after, end).split("\n")) {
      const match = line.match(/^      ([A-Za-z0-9_]+):\s*(.*)$/);
      if (match) scheme[match[1]] = parseScalar(match[2]);
    }
  }
  return { style, scheme };
}

export function applyMenu(yaml, pageSize) {
  const count = Number(pageSize);
  if (!Number.isInteger(count) || count < 1 || count > 9) {
    throw new Error("候选数要在 1 到 9");
  }
  let found = false;
  const next = yaml.replace(/^( *(?:"menu\/page_size"|menu\/page_size):\s*)\d+/m, (_all, prefix) => {
    found = true;
    return `${prefix}${count}`;
  });
  if (!found) throw new Error("找不到 menu/page_size");
  return next;
}
