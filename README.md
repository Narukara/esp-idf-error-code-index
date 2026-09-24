# ESP-IDF Error Code Index

ESP-IDF 生态错误码的**非官方观察索引**。记录组件源码已经定义的数值、BASE、条件和来源，为开发者查询及排查重叠提供证据。

本项目不分配、不预留错误码，不接受号码申请。“未观察到使用”不代表可安全使用；数值重叠不等于组件有缺陷，也不代表两个定义能在同一构建中生效。

## 当前范围

- 默认扫描 ESP-IDF `v5.5.1` 的 `esp_common`、`nvs_flash`、`esp_wifi`、`esp_http_client`、`esp_https_ota`、`esp-tls`，以及 Registry 中 `espressif/mdns`、`espressif/led_strip` 的最新稳定版本。这个固定 IDF tag 是起始观察基线，不代表最新版本。
- GitHub 按组件目录读取固定 commit 的源文件，不克隆整个 ESP-IDF。
- Registry 读取发布版本的 ZIP 包，不以仓库开发分支替代。
- 候选宏、简单枚举、多级 BASE、别名、常见整数及位运算；复杂表达式明确保留为未解析。
- Kconfig 表达式、条件和相关配置片段保留。默认值不会自动当成实际值。
- 增量扫描、可恢复的预算中断、历史结果、JSON/Markdown 报告、静态查询页面及 GitHub Actions。

首页以错误码空间为中心：完整 32 位有符号数值范围或低位区间视图、按大小压缩的竖向区段、组件及错误码详情，以及 BASE＋数量的区段重叠查询。空洞独立展示；BASE 标记不被扩展成假定占用的整块空间。扫描与解析信息集中在“数据与方法”页面。首页与数据页均支持中英文；右上角切换语言并保存本机偏好，也可使用 `?lang=zh` 或 `?lang=en` 分享指定语言的页面。静态页面默认英文；语言优先级为 URL 参数、已保存的手动选择、浏览器语言偏好列表中首个支持的语言，最后回退英文。中文地区标签（如 zh-CN、zh-TW）匹配中文。GitHub Pages 不执行服务端请求语言协商；浏览器环境检测在本地完成，不增加网络请求。组件名、符号和原始证据保持原文。

这不是全生态覆盖。来源清单、命名规则和排除目录共同限定扫描范围；没有 BASE 的宏也会被收录，但不匹配命名规则的错误域可能漏检。没有完整求解 Kconfig、C 预处理器、类型转换、跨组件 include 或依赖版本组合；未明确配置的跨组件引用会保留为未解析。暂不推断上游保留区间，也不证明项目级冲突。

## 快速运行

需要 Python 3.10+，运行工具及测试没有第三方 Python 依赖。在仓库根目录执行：

```console
python -m errindex scan
python -m errindex validate
python -m errindex build
python -m http.server 8000 --directory site
```

用浏览器打开 `http://localhost:8000`。页面只读取本地索引，不会触发上游扫描。

```console
python -m errindex scan --source espressif/mdns
python -m errindex scan --max-components 1
python -m errindex scan --refresh
python -m errindex scan --source idf/nvs_flash --force
python -m errindex scan --offline
python -m errindex report
python -m unittest discover -s tests -v
node --test tests/space.test.js tests/page.test.js tests/i18n.test.js
```

`--refresh` 忽略元数据的本地有效期，仍使用条件请求。`--force` 强制重新分析选定源码；可以与 `--refresh` 组合复核上游。`--offline` 禁止所有网络请求，需要已有元数据/源码缓存或可复用结果。所有扫描模式均遵守预算。

## 默认资源预算

| 项目 | 默认上限或策略 |
| --- | --- |
| 并发 | 1；请求间隔至少 1 秒 |
| 每次组件数 | 4，包含检查后复用的组件 |
| 每次 HTTP 请求 | 100 |
| 每次响应正文下载量 | 20 MiB |
| 单次响应 | 8 MiB |
| 扫描时间 | 240 秒；网络操作另受短超时限制 |
| 每组件候选文件 | 300 |
| 单个源码文件 | 512 KiB |
| 每组件读取源码总量 | 12 MiB |
| HTTP 缓存 | 128 MiB，扫描后清理较旧条目 |
| 元数据有效期 | 6 小时 |
| 自动重试 | 无；遇到限流停止本轮 |

预算可在 `config/sources.json` 中调整。网络限额针对应用读取的响应正文，不包括 TLS/HTTP 头开销。解压只读取选中的文本成员，不解压到任意磁盘路径，不执行第三方构建脚本。单个组件超过限制时报告失败，不把被截断的结果当成完整结果。

首次扫描可能分几轮完成。预算耗尽是正常的延期，`data/manifest.json` 保存下一来源；已完成组件立即落盘。再次运行优先继续延期来源，已经下载的文件从缓存读取。

## 文件筛选

每个来源可配置 `scan_mode`：

| 模式 | 文件范围 |
| --- | --- |
| `public-headers` | 静态读取 CMake 的 `INCLUDE_DIRS` 和错误码注册 `HEADERS`，选择公开头文件及其在组件内的递归 include；当前来源使用此模式 |
| `headers` | 所有候选头文件（含私有头文件）以及 CMake/Kconfig/manifest；新增来源未指定模式时的默认值 |
| `full` | 候选头文件及 `.c` / `.cpp` 实现文件；适合手动审计实现中的私有定义 |

三种模式均排除示例、测试（含 `host_test`）、内嵌 managed_components 等目录。不会执行 CMake；条件分支的字面路径取并集。遇到动态公开路径、生成头文件或无法识别的声明，会回退为全部头文件；不假装完成了公开接口识别。文件选择版本和来源模式参与增量指纹，改变模式会重新分析。

GitHub 只下载选中的文件；Registry 仍需下载整个 ZIP，选择性读取成员可减少解压与解析工作，但不会减少 ZIP 的传输量。公开头文件扫描可能遗漏实现文件中的错误定义，因此没有条目不是号码可用的证明。私有头文件也可能因公开头文件引用而被纳入。每次选择的文件数量、跳过数量和回退原因保存在来源证据中，并显示在数据页。

GitHub 来源默认拒绝包含子模块的组件。可用 `exclude_submodules` 明确列出组件目录内要跳过的子模块路径；其路径与固定提交记录在证据中，不下载、不宣称覆盖子模块内容。Wi-Fi 当前明确跳过 `lib`。

可用 `context_headers` 指定同一仓库、同一提交中的少量公共 `.h` 文件（最多 8 个），只用于求值，不把其定义重复登记为该组件所有。下载和文件预算仍包含这些文件。Wi-Fi 使用 `components/esp_common/include/esp_err.h` 解析公共 BASE；每条引用保留文件、行号、表达式及固定提交链接。不自动遍历跨仓库依赖，条件不明或定义冲突时仍保留为未解析。

## 数据与维护

| 路径 | 作用 |
| --- | --- |
| `config/sources.json` | 来源、固定版本/版本策略、维护方证据、命名规则和预算 |
| `config/overrides.json` | 精确限定来源、版本、文件及表达式的人工校正 |
| `errindex/` | 本地与 CI 共用工具 |
| `data/manifest.json` | 各来源当前接受结果、失败状态和续跑位置 |
| `data/components/` | 按分析指纹保存的历史观察结果 |
| `data/index.json` | 当前视图，供查询和下载 |
| `reports/` | 组件汇总和数值重叠报告 |
| `web/` | 无第三方前端依赖的页面源文件 |
| `.cache/` | 可删除的下载缓存、运行日志及发现候选，不提交 |
| `site/` | Pages 构建结果，不提交 |

源码身份、解析器版本、来源设置或相关人工规则变化，会使已有分析失效。未变化组件复用已提交数据；缓存只用于加速，缓存被清理不丢失已接受记录。重新求值后，汇总和重叠检查全量重建，以发现新旧组件之间的重叠。

未发生实质变化时不改时间戳、不生成无意义差异。每次成功检查的时间和资源统计写在 `.cache/last-run.json`；数据中的接受时间只在接受结果发生变化时更新。下载失败保留旧结果并标记，恢复成功会清除失败标记。

如需保证长期完整重算，应自行归档对应上游源码；本仓库保留文件哈希、定义表达式和来源证据，不永久镜像所有发布包。Registry 的 `component_hash` 和 ZIP 文件 SHA-256 分开记录，不假定二者使用相同计算方式。

## 添加来源

在 `config/sources.json` 的 `sources` 数组加入一个 Registry 组件或 GitHub 组件目录。可复制现有条目；第三方维护方默认填写 `unknown`，不要把“托管在官方 Registry”当成“Espressif 维护”。如果两个入口对应同一组件，优先选一个入口，避免重复观察被当成独立定义。

可选发现命令每次只读取一页，不自动加入扫描清单：

```console
python -m errindex discover --page 1
```

候选保存在 `.cache/discovered-sources.json`，经审查后选入清单。当前没有默认全 Registry / 全 GitHub 遍历。扩大清单前先评估包大小、文件数量和命名规则。

人工校正示例（示意，并非真实组件记录）：

```json
{
  "source": "vendor/component",
  "version": "1.2.3",
  "symbol": "ESP_ERR_EXAMPLE_END",
  "file": "include/example.h",
  "expression": "0x7001",
  "role": "error",
  "reason": "上游文档明确说明此值可以返回，不能作为边界标记排除",
  "evidence": "https://github.com/vendor/component/blob/COMMIT/include/example.h"
}
```

只接受事实校正和补充来源，不接受号码预留。上游表达式变化后，原规则不再匹配；应在更新 PR 中复核相关校正是否仍适用。

## GitHub Actions 和 Pages

1. 将仓库推送到 GitHub 的 `main` 分支。
2. 在 **Settings → Pages → Build and deployment** 中选择 **GitHub Actions**。
3. 在 **Settings → Actions → General** 中允许 GitHub Actions 创建 PR；组织策略可能需要管理员允许。
4. 手动运行 **Update observations** 验证首次更新，此后每周二运行一次。定时任务可能延迟。

更新流程使用相同命令，创建/更新 `automation/observations` 上的一个 PR。合并到 `main` 后才发布页面。常规工作是审查新数值、BASE 变化、未解析项、失败状态和新增重叠。

更新 PR 尚未合并时，下次运行会从该专用分支合并已完成的观察数据和续跑位置；仅读取 JSON，不执行其中的代码。请不要在这个机器人分支手工开发功能。需要撤销候选数据时，关闭 PR 并删除该分支，然后修改主分支来源/规则后重新运行。

`GITHUB_TOKEN` 创建的 PR 通常不会再次触发 PR 工作流，所以更新流程在创建 PR **之前**也运行测试、数据校验和页面构建。不启用自动合并；如分支保护强制要求另一个 PR 检查，可使用 GitHub App 方案或按组织策略人工处理。没有配置个人访问令牌的硬性要求。

手动修改扫描器、来源和规则的 PR 会运行离线检查；Pages 构建不会下载上游组件。详细扫描日志作为 Actions 产物保存 14 天，上游失败会让更新运行标记失败，同时仍可提交旧数据保留状态供审查。

## 依据

- [ESP-IDF 错误码注册说明](https://docs.espressif.com/projects/esp-idf/zh_CN/latest/esp32/api-reference/system/esp_err.html)
- [Registry API](https://components.espressif.com/apidocs/)
- [GitHub Actions 缓存](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)
- [Pages 自定义工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
