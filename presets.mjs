export const RIME_ICE = {
  id: "rime_ice",
  name: "雾凇拼音",
  repo: "iDvel/rime-ice",
  url: "https://github.com/iDvel/rime-ice",
};

export const WANXIANG_MODEL = {
  id: "wanxiang-lts-zh-hans",
  name: "万象语法模型",
  file: "wanxiang-lts-zh-hans.gram",
  url: "https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hans.gram",
  bytes: 418078764,
  grammar: {
    language: "wanxiang-lts-zh-hans",
    collocation_max_length: 6,
    collocation_min_length: 3,
    collocation_penalty: -14,
    non_collocation_penalty: -6,
    weak_collocation_penalty: -100,
    rear_penalty: -20,
  },
  translator: {
    contextual_suggestions: false,
    max_homophones: 8,
  },
};

function assertSchemaId(schemaId) {
  if (!/^[A-Za-z0-9_]+$/.test(schemaId)) throw new Error("方案 id 无效");
}

export function enableSchema(yaml, schemaId) {
  assertSchemaId(schemaId);
  if (new RegExp(`^\\s*-\\s+schema:\\s*${schemaId}(?:\\s*#.*)?\\s*$`, "m").test(yaml)) return yaml;
  const item = `    - schema: ${schemaId}`;
  const list = /^  schema_list:\s*$/m.exec(yaml);
  if (!list) {
    if (!/^patch:\s*$/m.test(yaml)) throw new Error("找不到 patch");
    return yaml.replace(/^patch:\s*$/m, `patch:\n  schema_list:\n${item}`);
  }
  const after = list.index + list[0].length;
  const boundary = yaml.slice(after).search(/\n  [A-Za-z_"#]/);
  const end = boundary < 0 ? yaml.length : after + boundary;
  const block = yaml.slice(list.index, end).replace(/\s*$/, "");
  return yaml.slice(0, list.index) + `${block}\n${item}` + yaml.slice(end);
}

export function disableSchema(yaml, schemaId) {
  assertSchemaId(schemaId);
  const pattern = new RegExp(`^\\s*-\\s+schema:\\s*${schemaId}(?:\\s*#.*)?\\s*$`);
  const lines = yaml.split("\n");
  let removed = false;
  const next = lines.filter((line) => {
    if (!pattern.test(line)) return true;
    removed = true;
    return false;
  });
  if (!removed) return yaml;
  if (!next.some((line) => /^\s*-\s+schema:\s*[^\s#]+/.test(line))) {
    throw new Error("方案列表里只有雾凇，停用后没有输入方案");
  }
  return next.join("\n");
}

function replaceBlock(yaml, key, lines) {
  const block = `  ${key}:\n${lines.join("\n")}`;
  const header = new RegExp(`^  ${key}:\\s*$`, "m").exec(yaml);
  if (!header) {
    if (!/^patch:\s*$/m.test(yaml)) throw new Error("找不到 patch");
    return yaml.replace(/^patch:\s*$/m, `patch:\n${block}`);
  }
  const after = header.index + header[0].length;
  const boundary = yaml.slice(after).search(/\n  [A-Za-z_"#]/);
  const end = boundary < 0 ? yaml.length : after + boundary;
  return yaml.slice(0, header.index) + block + yaml.slice(end);
}

function setKey(yaml, key, value) {
  const line = `  ${key}: ${value}`;
  const pattern = new RegExp(`^  ${key.replaceAll("/", "\\/")}:\\s*.*$`, "m");
  if (pattern.test(yaml)) return yaml.replace(pattern, line);
  const suffix = yaml.endsWith("\n") ? "" : "\n";
  return `${yaml}${suffix}${line}\n`;
}

export function applyGrammar(yaml, model = WANXIANG_MODEL) {
  const lines = Object.entries(model.grammar).map(([key, value]) => `    ${key}: ${value}`);
  let next = replaceBlock(yaml, "grammar", lines);
  for (const [key, value] of Object.entries(model.translator)) {
    next = setKey(next, `translator/${key}`, value);
  }
  return next;
}

export function applyPresets(files, { ice = null, wanxiang = false } = {}) {
  const next = { ...files };
  if (ice === true) {
    if (typeof next["default.custom.yaml"] !== "string") throw new Error("缺少 default.custom.yaml");
    next["default.custom.yaml"] = enableSchema(next["default.custom.yaml"], RIME_ICE.id);
  } else if (ice === false) {
    if (typeof next["default.custom.yaml"] !== "string") throw new Error("缺少 default.custom.yaml");
    next["default.custom.yaml"] = disableSchema(next["default.custom.yaml"], RIME_ICE.id);
  }
  if (wanxiang === true) {
    if (typeof next["rime_ice.custom.yaml"] !== "string") throw new Error("缺少 rime_ice.custom.yaml");
    next["rime_ice.custom.yaml"] = applyGrammar(next["rime_ice.custom.yaml"], WANXIANG_MODEL);
  }
  return next;
}

export function presetStatus(files) {
  const menu = files["default.custom.yaml"] || "";
  const ice = files["rime_ice.custom.yaml"] || "";
  return {
    ice: /^\s*-\s+schema:\s*rime_ice(?:\s*#.*)?\s*$/m.test(menu),
    wanxiang: /^\s*language:\s*"?wanxiang-lts-zh-hans"?\s*$/m.test(ice),
  };
}
