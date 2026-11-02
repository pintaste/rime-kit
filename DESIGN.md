---
name: 鼠须管配置
description: 深色台面旁边一张纸，纸上是鼠须管的候选窗。
colors:
  ink: "#141311"
  paper: "#ece7df"
  rail: "#1c1916"
  hint: "#c9c2b8"
  quiet: "#9c958b"
  control: "#221f1c"
  line: "#3a342c"
  cream: "#f4efe8"
  accent: "#f0c98a"
  ok: "#b7d7b0"
  err: "#f0a8a0"
  stage: "#d7dbe3"
  stage-dark: "#1c1f26"
  placeholder: "#4a453e"
  hair: "rgba(255, 255, 255, 0.06)"
typography:
  body:
    fontFamily: "PingFang SC, Hiragino Sans GB, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "-0.012em"
  title:
    fontFamily: "PingFang SC, Hiragino Sans GB, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.012em"
  headline:
    fontFamily: "PingFang SC, Hiragino Sans GB, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.012em"
  label:
    fontFamily: "PingFang SC, Hiragino Sans GB, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.4
  log:
    fontFamily: "PingFang SC, Hiragino Sans GB, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.45
rounded:
  control: "8px"
  tab: "10px"
  chip: "999px"
spacing:
  group: "10px"
  rail: "18px"
  pad: "28px"
components:
  button-deploy:
    backgroundColor: "{colors.line}"
    textColor: "{colors.cream}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
    height: "44px"
  button-quiet:
    backgroundColor: "{colors.rail}"
    textColor: "{colors.cream}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
    height: "44px"
  chip:
    backgroundColor: "{colors.control}"
    textColor: "{colors.hint}"
    rounded: "{rounded.chip}"
    padding: "0 14px"
    height: "44px"
  chip-selected:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.ink}"
    rounded: "{rounded.chip}"
    height: "44px"
  input:
    backgroundColor: "{colors.control}"
    textColor: "{colors.cream}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
    height: "44px"
---

# Design System: 鼠须管配置

## Overview

**Creative North Star: "墨色台面旁边的一张纸"**

台面是深色的，用来放开关和句子。旁边那张纸是候选窗预览，纸的颜色跟着皮肤走，不跟台面走。这一套是从现有页面抽出来的，不是新选的视觉世界。

密度偏高，因为同一屏要改外观，也要管方案。字是苹方，控件是 8px 圆角的深色块，选中的配色用一颗暖黄。

**Key Characteristics:**

- 台面深色，预览区单独换底。
- 一个暖黄只用来表示「当前选中」和键盘焦点。
- 会立刻写入的动作和只改预览的动作分成两组。
- 状态用一句话，按钮只用动词。

## Colors

台面用暖黑，文字用暖白，强调只用一处黄。

### Primary

- **暖黄** (`colors.accent`，`#f0c98a`)：当前配色芯片，以及键盘焦点环。不拿来做大面积底。

### Neutral

- **墨** (`colors.ink`，`#141311`)：页面底，以及选中芯片上的字。
- **纸白** (`colors.paper`，`#ece7df`)：台面上的正文。
- **栏** (`colors.rail`，`#1c1916`)：右侧栏的底。
- **说明** (`colors.hint`，`#c9c2b8`)：分组说明、状态。
- **弱** (`colors.quiet`，`#9c958b`)：字段名和记录。
- **控件** (`colors.control`，`#221f1c`)：输入、未选中芯片、分段的底。
- **线** (`colors.line`，`#3a342c`)：边框，也是实心按钮的底。
- **奶油** (`colors.cream`，`#f4efe8`)：按钮字，以及试打框的底。
- **成功** (`colors.ok`，`#b7d7b0`)：做成了。
- **失败** (`colors.err`，`#f0a8a0`)：没做成。
- **试纸** (`colors.stage`，`#d7dbe3`)：浅色皮肤后面的预览底。
- **夜纸** (`colors.stage-dark`，`#1c1f26`)：深色皮肤后面的预览底。
- **占位** (`colors.placeholder`，`#4a453e`)：试打框里的示例字。
- **发线** (`colors.hair`，`rgba(255, 255, 255, 0.06)`)：栏和配色区的分隔线。

**The One Yellow Rule.** 暖黄只出现在「现在选中的配色」和焦点环上。不要用它做第二个主按钮。

## Typography

**Body Font:** 苹方（PingFang SC，其次 Hiragino Sans GB）

**Character:** 系统里本来就有的中文，不另下一套展示字体。标题只比正文大一档。

### Hierarchy

- **Title**（600，20px，字距 -0.012em）：页面名「鼠须管配置」。
- **Headline**（600，16px）：「外观」「方案」。
- **Body**（400，15px，行高 1.45）：控件里的字。
- **Label**（400，13px）：说明、字段名、状态。
- **Log**（400，12px，行高 1.45）：部署记录。

## Layout

宽屏是两列：左边预览和配色，右边 300px 的栏。栏内两组，组内间距 10px，组与组 18px。窄于 760px 时改成上下：预览、配色、栏。栏内边距 28px 22px。

## Elevation & Depth

平时是平的。层次靠底色差：页面、栏、控件三层。预览里的候选窗有一道阴影，那是候选窗自己的，不是台面的卡片。

### Shadow Vocabulary

- **候选窗**（`0 10px 28px rgba(0, 0, 0, 0.28)`）：只用于预览里的候选窗。

**The Flat Desk Rule.** 按钮、芯片、输入框不加重阴影。

## Shapes

控件 8px，横排竖排的外框 10px，配色芯片是胶囊。

## Components

### Buttons

- **Shape:** 8px。
- **Primary:** 线色底、奶油字，高 44px。用于「保存外观」和方案动作。
- **Quiet:** 透明底、同色边。用于「撤回上次写入」。
- **Hover / Focus:** 按下缩小到 0.96；焦点是 2px 暖黄环。没有未保存的改动时，保存按钮变淡且不可按。

### Chips

- **Style:** 控件底、说明色字、胶囊。
- **State:** 选中为暖黄底、墨色字。

### Inputs / Fields

- **Style:** 控件底、奶油字、8px、高 44px。试打框是奶油底、墨色字。
- **Focus:** 2px 暖黄环。
- **Disabled:** 透明度 0.55，光标保持默认，不用等待光标冒充加载。

## Do's and Don'ts

### Do:

- **Do** 把「现在是什么」和「下一步按钮」分成两处。
- **Do** 只改预览的控件和马上写入的控件分成「外观」和「方案」。
- **Do** 用现有这些颜色变量，不要在台面上另写一套十六进制。

### Don't:

- **Don't** 把候选窗皮肤的颜色收进台面变量。预览必须照皮肤本身画，包括那套皮肤对比不够的时候。
- **Don't** 用暖黄做大块背景。
- **Don't** 为了这一页再造一套组件库。
