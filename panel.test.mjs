import assert from "node:assert/strict";
import test from "node:test";
import { applyMenu, applyPatch, previewInput, resolvePanel } from "./panel.mjs";

test("配色没写字体时沿用全局字体", () => {
  const panel = resolvePanel(
    {
      font_face: "LXGW ZhenKai Slab GB",
      corner_radius: 12.5,
      border_height: -3,
      border_width: 0,
    },
    { name: "macOS 深色", back_color: "0x26000000" },
  );
  assert.equal(panel.fontFace, "LXGW ZhenKai Slab GB");
});

test("配色写了字体时覆盖全局字体", () => {
  const panel = resolvePanel(
    { font_face: "LXGW ZhenKai Slab GB" },
    { font_face: "PingFang SC" },
  );
  assert.equal(panel.fontFace, "PingFang SC");
});

test("内边距是边框加上圆角，负数往里收", () => {
  const panel = resolvePanel(
    { corner_radius: 12.5, border_height: -3, border_width: 0 },
    {},
  );
  assert.deepEqual(panel.edgeInset, { width: 12.5, height: 9.5 });
});

test("字竖排时内边距宽高对调", () => {
  const panel = resolvePanel(
    {
      corner_radius: 12.5,
      border_height: -3,
      border_width: 0,
      text_orientation: "vertical",
    },
    {},
  );
  assert.deepEqual(panel.edgeInset, { width: 9.5, height: 12.5 });
});

test("行内拼音时候选窗不包含拼音行", () => {
  const panel = resolvePanel({ inline_preedit: true }, {});
  assert.equal(panel.preedit, null);
});

test("阴影只标在高亮候选上", () => {
  const panel = resolvePanel({ shadow_size: 2 }, {});
  assert.equal(panel.highlightShadow, 2);
  assert.equal(panel.panelShadow, 0);
});

test("保存时浅色和深色都改成选中的配色", () => {
  const yaml = [
    "patch:",
    "  style/color_scheme: macos_dark",
    "  style/color_scheme_dark: macos_dark",
    "  show_notifications_when: appropriate",
    "",
  ].join("\n");
  const next = applyPatch(yaml, { scheme: "wechat_light", layout: "stacked", font: "LXGW ZhenKai Slab GB" });
  assert.match(next, /^  style\/color_scheme: wechat_light$/m);
  assert.match(next, /^  style\/color_scheme_dark: wechat_light$/m);
  assert.match(next, /^  show_notifications_when: appropriate$/m);
});

test("保存时写入排列和字体", () => {
  const yaml = [
    "patch:",
    '  style/candidate_list_layout: stacked',
    '  style/font_face: "LXGW ZhenKai Slab GB"',
    '  style/label_font_face: "LXGW ZhenKai Slab GB"',
    "",
  ].join("\n");
  const next = applyPatch(yaml, { scheme: "macos_dark", layout: "linear", font: "LXGW WenKai" });
  assert.match(next, /^  style\/candidate_list_layout: linear$/m);
  assert.match(next, /^  style\/font_face: "LXGW WenKai"$/m);
  assert.match(next, /^  style\/label_font_face: "LXGW WenKai"$/m);
});

test("保存时只改选中配色自己的字体", () => {
  const yaml = [
    "patch:",
    '  style/font_face: "PingFang SC"',
    "  preset_color_schemes:",
    "    wechat_light:",
    "      font_face: PingFangSC # 候选词字体",
    "    wechat_dark:",
    "      font_face: PingFangSC # 候选词字体",
    "",
  ].join("\n");
  const next = applyPatch(yaml, { scheme: "wechat_light", layout: "stacked", font: "LXGW WenKai" });
  assert.match(next, /^    wechat_light:\n      font_face: "LXGW WenKai" # 候选词字体$/m);
  assert.match(next, /^    wechat_dark:\n      font_face: PingFangSC # 候选词字体$/m);
});

test("配色写了排列时覆盖全局排列", () => {
  const panel = resolvePanel(
    { candidate_list_layout: "stacked" },
    { candidate_list_layout: "linear" },
  );
  assert.equal(panel.layout, "linear");
});

test("保存时只改选中配色自己的排列", () => {
  const yaml = [
    "patch:",
    "  style/candidate_list_layout: stacked",
    "  preset_color_schemes:",
    "    my:",
    "      candidate_list_layout: linear",
    "    my_dark:",
    "      candidate_list_layout: linear",
    "",
  ].join("\n");
  const next = applyPatch(yaml, { scheme: "my", layout: "stacked", font: "PingFang SC" });
  assert.match(next, /^    my:\n      candidate_list_layout: stacked$/m);
  assert.match(next, /^    my_dark:\n      candidate_list_layout: linear$/m);
});

test("补丁里的配色字体盖过全局，边距仍用全局圆角", () => {
  const yaml = [
    "patch:",
    '  style/font_face: "LXGW WenKai"',
    "  style/corner_radius: 12.5",
    "  style/border_height: -3",
    "  style/border_width: 0",
    "  style/inline_preedit: true",
    "  style/shadow_size: 2",
    "  style/candidate_list_layout: stacked",
    "  style/line_spacing: 10",
    "  preset_color_schemes:",
    "    wechat_light:",
    "      font_face: PingFangSC # 候选词字体",
    "      back_color: 0xFFFFFF",
    "    wechat_dark:",
    "      font_face: PingFangSC",
    "",
  ].join("\n");
  const light = previewInput(yaml, "wechat_light");
  const panel = resolvePanel(light.style, light.scheme);
  assert.equal(panel.fontFace, "PingFangSC");
  assert.deepEqual(panel.edgeInset, { width: 12.5, height: 9.5 });
  assert.equal(panel.preedit, null);
  assert.equal(panel.highlightShadow, 2);
  assert.equal(panel.lineSpacing, 10);
  assert.equal(light.scheme.back_color, "0xFFFFFF");
  assert.equal(previewInput(yaml, "wechat_dark").scheme.font_face, "PingFangSC");
});

test("保存时写入每页候选数，其它行不动", () => {
  const yaml = [
    "patch:",
    "  schema_list:",
    "    - schema: rime_ice",
    '  "menu/page_size": 8',
    "",
  ].join("\n");
  const next = applyMenu(yaml, 5);
  assert.match(next, /^  "menu\/page_size": 5$/m);
  assert.match(next, /^    - schema: rime_ice$/m);
});

test("候选数没变也算找到，缺这一行才报错", () => {
  const yaml = 'patch:\n  "menu/page_size": 9\n';
  assert.equal(applyMenu(yaml, 9), yaml);
  assert.throws(() => applyMenu("patch:\n", 5), /找不到 menu\/page_size/);
});

test("保存时写入拼音是否留在行内和字号", () => {
  const yaml = [
    "patch:",
    "  style/inline_preedit: true",
    "  style/font_point: 16",
    "  style/label_font_point: 12",
    "",
  ].join("\n");
  const next = applyPatch(yaml, {
    scheme: "macos_dark",
    layout: "linear",
    font: "PingFang SC",
    style: { inline_preedit: false, font_point: 18, label_font_point: 14 },
  });
  assert.match(next, /^  style\/inline_preedit: false$/m);
  assert.match(next, /^  style\/font_point: 18$/m);
  assert.match(next, /^  style\/label_font_point: 14$/m);
});

test("缺样式键时补写，不再静默跳过", () => {
  const yaml = [
    "patch:",
    "  show_notifications_when: appropriate",
    "",
  ].join("\n");
  const next = applyPatch(yaml, {
    scheme: "macos_dark",
    layout: "linear",
    font: "PingFang SC",
    style: { font_point: 18 },
  });
  assert.match(next, /^  style\/candidate_list_layout: linear$/m);
  assert.match(next, /^  style\/font_face: "PingFang SC"$/m);
  assert.match(next, /^  style\/font_point: 18$/m);
  assert.match(next, /^  show_notifications_when: appropriate$/m);
});

test("样式行尾注释在保存后保留", () => {
  const yaml = ["patch:", "  style/font_point: 16 # 字号", ""].join("\n");
  const next = applyPatch(yaml, { scheme: "macos_dark", layout: "linear", font: "PingFang SC", style: { font_point: 18 } });
  assert.match(next, /^  style\/font_point: 18 # 字号$/m);
});

test("配置里没有这个皮肤时写入完整定义", () => {
  const yaml = ["patch:", "  style/font_point: 16", ""].join("\n");
  const definition = {
    id: "macos_dark",
    name: "macOS 深色",
    corner_radius: 12.5,
    back_color: "0x26000000",
    candidate_text_color: "0xE6FFFFFF",
  };
  const next = applyPatch(yaml, { scheme: "macos_dark", layout: "stacked", font: "PingFang SC", definition });
  assert.match(next, /^  preset_color_schemes:$/m);
  assert.match(next, /^    macos_dark:$/m);
  assert.match(next, /^      name: "macOS 深色"$/m);
  assert.match(next, /^      back_color: 0x26000000$/m);
  assert.equal(previewInput(next, "macos_dark").scheme.back_color, "0x26000000");
});
