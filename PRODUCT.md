# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

macOS 上用鼠须管的人。两种情况都算：已经装好、要在自己电脑上改候选窗和方案的人；以及从零开始、还没有方案和语法模型的人。作者会把仓库发到 GitHub，克隆来用的人与作者是同一类使用者。

## Product Purpose

在本机打开一个页面，看见鼠须管的候选窗，改皮肤、排列、字体和候选数，开关雾凇拼音与万象语法模型，并在页面里试打。写入已有的 Rime 配置后重新部署。对还没有这些文件的电脑，这个页面还要能把方案和语法模型装上。成功是：改完之后仍能打中文，页面上的预览和试打与刚部署的输入法一致。

## Positioning

同一个页面既预览真实候选窗，又把改动部署进鼠须管，并给没有方案的电脑装上雾凇和万象模型。plum 只装包，不预览候选窗；只改 yaml 的工具则不负责把方案和模型装上来。

## Operating Context

在 macOS 上运行 `python3 server.py`，打开 http://127.0.0.1:8766 。不设 `RIME_USER_DIR` 时读写 `~/Library/Rime` 并部署 `/Library/Input Methods/Squirrel.app`。`RIME_USER_DIR` 指向别的目录时只改那一份，不部署本机输入法。每次改动先备份再部署，备份在 `backups/`。用页面底部的输入框试打，输入法是系统里的鼠须管，不是页面模拟的候选。

## Capabilities and Constraints

已有：

- 预览候选窗：配色、横排或竖排、字体、候选词字号、序号字号、每页候选数、拼音留在光标那一行还是候选窗顶上。
- 启用或停用雾凇拼音。停用只从 `default.custom.yaml` 的方案列表去掉 `rime_ice`，其它方案不动。列表里只剩雾凇时拒绝停用。
- 启用或停用万象语法模型。停用写回本工具启用前保存的 `rime_ice.custom.yaml`。不是在这里启用的，没有那份备份，就不猜原来的模型。
- 保存外观，撤回上次写入。部署失败把改过的文件和日志收回，并丢掉坏的 `build/default.yaml` 再按收回后的文件部署。安装失败同样收回这次写入的文件。
- 页面上有一个输入框，用系统里现在的鼠须管打字。上面的候选窗是预览，不是正在用的输入法。
- 缺少 `rime_ice.schema.yaml` 时，从 https://github.com/iDvel/rime-ice 下载并写入方案文件，再把 `rime_ice` 加进方案列表。缺少 `wanxiang-lts-zh-hans.gram` 时，从官方配方地址下载该文件（418078764 字节），再写万象语法补丁。缺哪个装哪个。下载可取消，取消会删掉半成品。已有皮肤、`custom_phrase.txt` 和个人补丁不覆盖；雾凇仓库里的词库、lua 和方案文件可以替换。

约束：

- 只做 macOS 鼠须管，不做 Windows 小狼毫。
- 个人配置不进仓库。模型二进制不进仓库。
- 不调用 plum。模型只从 `https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hans.gram` 下载。

## Brand Commitments

名称是「鼠须管配置」。界面文案使用简体中文，控件直接写它做的事。

## Evidence on Hand

- `README.md`、`index.html`、`server.py`、`install.py`、`panel.mjs`、`presets.mjs`
- `fixtures/` 里的示例配置，不是任何人的现用配置
- `panel.test.mjs`、`presets.test.mjs`、`test_isolated.py`
- 没有用户评价、价格或对外许可声明。不要编造。

## Product Principles

- 一次改动失败之后，输入法必须回到还能打中文的状态。
- 停用只撤销这个工具自己写过的内容，不猜测使用者原来的模型。
- 个人配置和模型文件留在本机，不进入仓库。
- 预览和试打都对着真实的鼠须管，不另做一套候选逻辑。
- 只服务 macOS 鼠须管。
