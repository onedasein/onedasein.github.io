# 我的博客 · Jekyll + Chirpy + GitHub Pages

用 [Chirpy Starter](https://github.com/cotes2020/chirpy-starter) 搭的静态博客，push 后由 GitHub Actions 自动构建并发布到 GitHub Pages。

## 技术栈（实测）

| 层 | 用什么 |
|---|---|
| 主题 | `jekyll-theme-chirpy` **~> 7.6**（gem 远程主题，主题源码不在本仓库） |
| 生成器 | Jekyll（Ruby + Bundler） |
| 托管 | GitHub Pages（**Source = GitHub Actions**，不是 branch 部署） |
| CI | `.github/workflows/pages-deploy.yml`（Ruby 3.4 → `jekyll build` → `htmlproofer` → `deploy-pages`） |
| 写作用 | Markdown + YAML front matter |

> 注意：**本方案不需要 Node/npm**。JS/CSS 产物由主题 gem 自带；只有当你 fork 整套主题源码（改 `_javascript/`、用 Rollup）时才需要 Node。

## 一、上线三步

```bash
# 1. 填你自己的信息（用户名 / 署名 / 邮箱，可选域名）
bash tools/init-site.sh -u <你的GitHub用户名> -n "<你的名字>" -e you@example.com

# 2. 推到 GitHub（仓库名必须是 <用户名>.github.io，否则见下面「项目站点」）
git add -A && git commit -m "chore: init site"
git remote add origin git@github.com:<用户名>/<用户名>.github.io.git
git push -u origin main

# 3. 打开仓库 → Settings → Pages → Source 选 "GitHub Actions"
```

之后每次 `git push`，Actions 会自动构建发布。访问 `https://<用户名>.github.io`。

**仓库名不是 `<用户名>.github.io` 时**（项目站点，站点落在 `/<仓库名>` 子路径），必须设 `baseurl`：

```bash
bash tools/init-site.sh -u <用户名> -r <仓库名>    # 会自动写 baseurl: "/<仓库名>"
```
漏设 `baseurl` 的典型症状：页面能打开但 **CSS/JS 全 404，样式全丢**。

## 二、本地预览

```bash
bash tools/local-preview.sh            # → http://127.0.0.1:4000（自动装依赖，首次较慢）
bash tools/local-preview.sh --build    # 只做生产构建（产出 _site/）
```

> 本机上 `blog/.blog-env/` 里已经放了一套**实测构建通过**的隔离 Ruby 环境（约 85 MB，已 gitignore），
> 所以直接跑上面两条命令即可，不用额外装 `ruby-dev`。换到别的机器时脚本会自动重建这套环境。
{: .prompt-info }

依赖全部装在仓库内的 `.blog-env/`（已 gitignore），**不写系统目录、不需要 sudo**。
想换位置：`BLOG_DEV_HOME=~/chirpy-env bash tools/local-preview.sh`。

需要 Ruby ≥ 3.1（CI 用 3.4），且要有 Ruby 开发头文件（`sudo apt install ruby-dev build-essential`），
因为 `json`、`bigdecimal`、`eventmachine` 这些依赖带 C 扩展、必须现场编译。缺头文件时脚本会提示，
也可以绕开本地环境用 Docker：

```bash
docker run --rm -v "$PWD":/srv/jekyll -p 4000:4000 jekyll/jekyll jekyll serve --host 0.0.0.0
```

若本机已有完整 Ruby 环境，直接用 Chirpy 官方脚本即可：`bash tools/run.sh`。

## 三、写文章

新建 `_posts/YYYY-MM-DD-slug.md`：

```markdown
---
title: 文章标题
date: 2026-09-14 20:30:00 +0800
categories: [技术, 折腾]
tags: [jekyll, github-pages]
description: 一句话摘要，会显示在首页列表和 SEO 描述里。
---

正文用 Markdown 写。
```

- 草稿放 `_drafts/`（不发布），`--drafts` 预览
- 头图：front matter 加 `image: /assets/img/xxx.png`
- 置顶：加 `pin: true`
- 排版速查（提示块、代码块标题、图片等）：见官方 [Writing a New Post](https://github.com/cotes2020/jekyll-theme-chirpy/wiki/Writing-a-New-Post)

## 四、目录说明

```
_config.yml                 站点全部配置（改完 push 才生效）
_data/contact.yml           侧栏社交图标（Twitter 默认已注释，按需打开）
_tabs/                      关于/归档/分类/标签 这几个页面
_posts/                     你的文章
index.html                  首页（layout: home）
_plugins/posts-lastmod-hook.rb  用 git 提交时间显示「最后修改」
tools/init-site.sh          一次性占位符替换
tools/local-preview.sh      本机预览
tools/run.sh tools/test.sh  Chirpy 官方脚本（预览 / 构建+检查）
.github/workflows/pages-deploy.yml   部署流水线
```

## 五、自定义域名（可选）

1. DNS 加记录（GitHub Pages 官方 IP/域名）：
   - 根域：`A` → `185.199.108.153` / `.109.153` / `.110.153` / `.111.153`
   - `www`：`CNAME` → `<用户名>.github.io`
2. Settings → Pages → Custom domain 填域名，保存后等 DNS 校验通过
3. 证书签发后勾上 **Enforce HTTPS**
4. 把 `_config.yml` 的 `url` 改成 `https://你的域名`（Actions 部署**不需要** CNAME 文件）

之后再改邮箱/名字，直接编辑 `_config.yml` 即可。

## 六、可选增强

- **评论（giscus，无后端）**：去 https://giscus.app 生成 4 个值，填进 `_config.yml` 的 `comments.giscus`，并把 `provider` 设为 `giscus`（仓库需为 public 并开启 Discussions）
- **统计**：`_config.yml` 的 `analytics` 支持 Google / Umami / Cloudflare / GoatCounter / Matomo / Fathom
- **自托管静态资源（去掉 CDN 依赖）**：
  ```bash
  git submodule update --init assets/lib
  ```
  再把 `_config.yml` 里 `assets.self_host.enabled` 设为 `true`，并在 workflow 的 `actions/checkout` 打开 `submodules: true`
- **更新主题**：改 `Gemfile` 里的 `gem "jekyll-theme-chirpy", "~> 7.6"` 版本号，重新 push 即可
- **浏览器里写作**：仓库自带 `.devcontainer/`，可用 Codespaces 一键开环境；或按 `.` 打开 github.dev 直接编辑

## 七、常见坑

| 症状 | 原因 |
|---|---|
| CSS/JS 全 404 | 项目站点没设 `baseurl` |
| 文章「最后修改」时间不对 | checkout 没加 `fetch-depth: 0`（本仓库已配好） |
| 部署报权限错 | Settings → Pages 的 Source 没选 GitHub Actions，或 workflow 缺 `pages: write` / `id-token: write` |
| push 了没更新 | `paths-ignore` 忽略了 `.gitignore`/`README.md`/`LICENSE`，只改这些文件不会触发构建 |
| 本地构建缺 gem | 用 `tools/local-preview.sh`（依赖装在仓库内），别混用系统 bundler 和它 |
| 构建时打印 `fatal: ambiguous argument 'HEAD'` | 仓库还没有任何提交，`_plugins/posts-lastmod-hook.rb` 取不到 git 历史；提交一次即消失（不影响构建结果） |
| 文章 push 了却没出现 | front matter 的 `date` 是未来时间，Jekyll 默认不发布「未来文章」 |

## 八、参考

- 主题文档：<https://github.com/cotes2020/jekyll-theme-chirpy/wiki>
- Starter 模板：<https://github.com/cotes2020/chirpy-starter>
- GitHub Pages 文档：<https://docs.github.com/pages>

本仓库基于 Chirpy Starter（MIT License，见 `LICENSE`）。
