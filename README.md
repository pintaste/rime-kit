# 鼠须管配置

macOS 鼠须管的本地配置页。需要已安装的鼠须管、Python 3 和 Node.js；安装雾凇拼音还要系统里的 `git`（Xcode 命令行工具自带）。左边预览候选窗，保存后才写入外观。雾凇拼音和万象语法模型点了马上生效。不含个人配置。

```sh
python3 server.py
```

打开 http://127.0.0.1:8766 。只能用 127.0.0.1 或 localhost 访问；写入请求要带页面自己取到的令牌，别的网页发来的请求会被拒绝。先打开一次鼠须管，让它生成 `squirrel.custom.yaml` 和 `default.custom.yaml`；这两份不在时页面能开，但不能保存。不设 `RIME_USER_DIR` 时，读写 `~/Library/Rime`。没有这个目录时，页面只展示仓库里的示例，保存、安装和撤回都会拒绝。`RIME_USER_DIR` 指向别的目录时只改那一份，不部署本机输入法。

外观（横排、字号、字体、配色）先改预览，要点「保存外观」才写入。雾凇和万象各自有一行状态；按钮只写下一步：「启用」「停用」或「安装」。安装由页面自己下载：雾凇来自 https://github.com/iDvel/rime-ice ，万象模型来自 https://github.com/amzxyz/RIME-LMDG 的 LTS 配方，约 399MB。缺哪个装哪个。不覆盖已有皮肤、`custom_phrase.txt` 和个人补丁。停用雾凇只从方案列表去掉 `rime_ice`，其它方案不动。如果列表里只剩雾凇，停用会拒绝，否则鼠须管会因没有输入方案而部署失败。停用万象写回本工具启用前保存的那份 `rime_ice.custom.yaml`；如果不是在这里启用的，没有那份备份，就不会猜原来的模型。「撤回上次写入」回到最近一次真正写入之前：改过的文件复原，这次新装的文件删掉，包括雾凇的词库、lua 和模型。每次改动先备份再部署，部署失败会把文件和日志收回。备份在 `backups/`，已忽略，不会进仓库。

```sh
node --test panel.test.mjs presets.test.mjs
python3 test_page.py
python3 test_http.py
python3 test_isolated.py
python3 test_install.py
```

预设：

| 选项 | 来源 | 写入 |
|---|---|---|
| 雾凇拼音 | https://github.com/iDvel/rime-ice | `default.custom.yaml` 的方案列表，不删已有方案 |
| 万象语法模型 | https://github.com/amzxyz/RIME-LMDG （LTS 配方里的 `wanxiang-lts-zh-hans.gram`，418078764 字节） | `rime_ice.custom.yaml` 的 `grammar`，以及 `contextual_suggestions`、`max_homophones` |

模型文件不放进仓库。页面只在本机缺少该文件时下载。

许可：MIT。
