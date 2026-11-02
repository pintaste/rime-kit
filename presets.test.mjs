import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  RIME_ICE,
  WANXIANG_MODEL,
  applyGrammar,
  applyPresets,
  disableSchema,
  enableSchema,
  presetStatus,
} from "./presets.mjs";

test("启用雾凇时保留原来的方案和候选数", () => {
  const yaml = [
    "patch:",
    "  # 方案列表",
    "  schema_list:",
    "    - schema: luna_pinyin",
    "",
    '  "menu/page_size": 8',
    "",
  ].join("\n");
  const next = enableSchema(yaml, RIME_ICE.id);
  assert.match(next, /^    - schema: luna_pinyin$/m);
  assert.match(next, /^    - schema: rime_ice$/m);
  assert.match(next, /^  "menu\/page_size": 8$/m);
  assert.equal(enableSchema(next, RIME_ICE.id), next);
  assert.equal(enableSchema(next, RIME_ICE.id), next);
  const off = disableSchema(next, RIME_ICE.id);
  assert.match(off, /^    - schema: luna_pinyin$/m);
  assert.doesNotMatch(off, /rime_ice/);
  assert.match(off, /^  "menu\/page_size": 8$/m);
  assert.throws(() => disableSchema("patch:\n  schema_list:\n    - schema: rime_ice\n", RIME_ICE.id), /只有雾凇/);
});

test("万象模型只改语法和指定的翻译项", () => {
  const yaml = [
    "patch:",
    "  grammar:",
    "    language: amz-v2n3m1-zh-hans",
    "    collocation_max_length: 5",
    "    collocation_min_length: 2",
    "  translator/contextual_suggestions: true",
    "  translator/max_homophones: 7",
    "  translator/max_homographs: 7",
    "",
  ].join("\n");
  const next = applyGrammar(yaml);
  assert.match(next, /^    language: wanxiang-lts-zh-hans$/m);
  assert.match(next, /^    collocation_max_length: 6$/m);
  assert.match(next, /^    collocation_min_length: 3$/m);
  assert.match(next, /^    collocation_penalty: -14$/m);
  assert.match(next, /^  translator\/contextual_suggestions: false$/m);
  assert.match(next, /^  translator\/max_homophones: 8$/m);
  assert.match(next, /^  translator\/max_homographs: 7$/m);
  assert.doesNotMatch(next, /amz-v2n3m1/);
});

test("两个预设只写到临时目录", async () => {
  assert.equal(WANXIANG_MODEL.bytes, 418078764);
  assert.equal(WANXIANG_MODEL.file, "wanxiang-lts-zh-hans.gram");
  assert.equal(RIME_ICE.repo, "iDvel/rime-ice");
  const dir = await mkdtemp(join(tmpdir(), "rime-kit-"));
  try {
    const files = {
      "default.custom.yaml": "patch:\n  schema_list:\n    - schema: luna_pinyin\n",
      "rime_ice.custom.yaml": "patch:\n  grammar:\n    language: amz-v2n3m1-zh-hans\n  translator/max_homographs: 7\n",
    };
    const applied = applyPresets(files, { ice: true, wanxiang: true });
    for (const [name, text] of Object.entries(applied)) {
      const path = join(dir, name);
      assert.equal(path.startsWith(`${dir}/`), true);
      await writeFile(path, text);
    }
    const written = await readFile(join(dir, "rime_ice.custom.yaml"), "utf8");
    assert.match(written, /language: wanxiang-lts-zh-hans/);
    const enabled = await readFile(join(dir, "default.custom.yaml"), "utf8");
    assert.match(enabled, /schema: rime_ice/);
    assert.match(enabled, /schema: luna_pinyin/);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("已启用和未启用都从配置文本判断", () => {
  const off = presetStatus({
    "default.custom.yaml": "patch:\n  schema_list:\n    - schema: luna_pinyin\n",
    "rime_ice.custom.yaml": "patch:\n  grammar:\n    language: amz-v2n3m1-zh-hans\n",
  });
  assert.deepEqual(off, { ice: false, wanxiang: false });
  const on = presetStatus(applyPresets({
    "default.custom.yaml": "patch:\n  schema_list:\n    - schema: luna_pinyin\n",
    "rime_ice.custom.yaml": "patch:\n  grammar:\n    language: amz-v2n3m1-zh-hans\n",
  }, { ice: true, wanxiang: true }));
  assert.deepEqual(on, { ice: true, wanxiang: true });
});

test("带行尾注释的方案项也算启用", () => {
  const yaml = "patch:\n  schema_list:\n    - schema: rime_ice # 常用\n";
  assert.equal(presetStatus({ "default.custom.yaml": yaml }).ice, true);
  assert.equal(enableSchema(yaml, "rime_ice"), yaml);
  assert.throws(() => disableSchema(yaml, "rime_ice"), /只有雾凇/);
});
