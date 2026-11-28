# 内容自检（TypeScript）

把「已经踩过一次的坑」固化成可执行规则，跑在 CI 里，让同一类事故不可能再发生第二次。

## 用

```bash
pnpm install          # 首次
pnpm check            # 类型检查 + 内容自检
pnpm check:content    # 只跑内容自检
pnpm check:types      # 只跑 tsc --noEmit
node tools/check-content.ts --explain   # 看每条规则存在的理由
node tools/check-content.ts --root <目录> --json   # 换根目录 / 机器可读输出
```

退出码：有 error → 1，只有 warning 或全绿 → 0。CI 里 `pages-deploy.yml` 会在 Ruby 构建之前先跑它（fail fast）。

## 本地 pre-commit 钩子

`.githooks/pre-commit` 在提交前跑一遍 `check:content`，把会让 CI 整体失败的几类问题挡在本地 —— 起因是一次提交把 `_posts/2026-09-14-hello-world.md` 首行的 `---` 并进了 `title:`，front matter 整段失效，本地没检查、CI 的 `Check content` 直接失败，Pages 也就没部署。

```bash
git config core.hooksPath .githooks   # 克隆后做一次（本仓库已设置）
git commit --no-verify                # 确实要跳过时
```

钩子对 Node 版本有要求：脚本是 `.ts`，靠 Node 自带的类型剥离直接运行，需要 **Node >= 23.6**。发行版打包的 Node 22 编译时没带 TypeScript 支持，会报 `ERR_NO_TYPESCRIPT` —— 那个报错看起来像脚本坏了，其实是运行时太旧。根目录的 `.node-version` 写着与 CI 一致的版本，钩子会自动在 PATH 里挑一个够新的 `node`，找不到时才报错。

## 五条规则及其来源

| 规则 | 严重级 | 编码的事故 |
|---|---|---|
| `posts/filename` | error | `_posts/2026-09-23.md` 因缺 slug 不被 Jekyll 认作文章，改内容永远不上线 |
| `posts/front-matter` | error | front matter 写 `+8000` 非法偏移，Ruby `Time.parse` 抛 `utc_offset out of range`，Jekyll 静默回退文件名日期 |
| `posts/https-links` | error | html-proofer 5 即使 `--disable-external` 也把 `http://` 判为失败 |
| `tabs/locale-keys` | error | 自定义 tab 缺 locale 键 → `tabs[page.title\|downcase]` 取空 → 页面 `<title>` 渲染为空 |
| `tabs/order` | warning | `collections.tabs.sort_by: order`，缺失/重复导致侧栏位置不确定 |

## 为什么用 TypeScript 而不是 shell

`posts/https-links` 这条最能说明问题：要先剥掉围栏代码块与行内代码（否则讲解 `http://` 的代码片段会被自己误伤），再按行号定位，还要放行回环地址。这类「先建模、再判断」的工作在 shell 里写不好，而 TS 的类型能把中间状态钉死：

- `splitFrontMatter` 返回 `data: unknown` —— 强制调用方先用 zod 校验，不能直接当对象用；
- schema 是唯一事实源，`z.infer` 推导类型，运行时校验与静态类型不可能打架；
- `strict` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` 让 `groups[key]`、`argv[i+1]` 这类取值都必须显式处理 `undefined`。

## 加一条新规则

1. 在 `tools/lib/schema.ts` 里用 zod 描述新格式（如果涉及新文件类型）；
2. 在 `tools/lib/rules.ts` 里加一个 `Rule`：必须有 `id`、`rationale`、`run`；
3. 把它加进文件末尾的 `ruleList`（`satisfies readonly Rule[]` 会替你检查形状）。

`rationale` 不是装饰：它要求你说清「这条规则防的是哪次事故」。

## 运行环境

Node 原生剥离类型（≥23.6），所以 `node tools/check-content.ts` 直接跑 `.ts`，**没有构建步骤**。类型检查是独立的一步（`tsc --noEmit`，TypeScript 7）。`erasableSyntaxOnly` 保证代码只用到可剥离的语法。
