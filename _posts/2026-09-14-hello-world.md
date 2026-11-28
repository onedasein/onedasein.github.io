---
title: 开张：这个博客是怎么搭起来的
date: 2026-09-14 09:00:00 +0800
categories: [随笔]
tags: [jekyll, chirpy, github-pages]
description: 记录本站的技术选型与上线流程：Jekyll + Chirpy 主题 + GitHub Actions 自动部署到 GitHub Pages，零服务器成本。
---

这是本站的第一篇文章，顺便把"怎么搭的"记下来，以后要复刻或迁移时不用重新查资料。

## 技术选型

| 部分 | 选择 | 为什么 |
| --- | --- | --- |
| 生成器 | Jekyll | GitHub Pages 原生支持，Ruby 生态成熟 |
| 主题 | Chirpy | 自带暗色模式、目录、标签归档、PWA，技术写作够用 |
| 托管 | GitHub Pages | 免费、自带 HTTPS、可绑自定义域名 |
| 部署 | GitHub Actions | 不受 Pages 插件白名单限制，push 即发布 |

需要配套的技术其实只有三样：**Git**（版本管理）、**Markdown**（写作）、**YAML**（配置和 front matter）。CI 那一层只要会读 workflow 文件就够了。

> 主题用 gem 远程引入（Chirpy Starter 方案），仓库里只有配置和内容，主题升级只需改一行版本号。
{: .prompt-info }

## 上线流程

1. 建仓库 `<用户名>.github.io`，把本站文件推上去
2. 仓库 **Settings → Pages → Source** 选 `GitHub Actions`
3. 等 Actions 跑完，访问 `https://<用户名>.github.io`

之后写文章的循环就三步：

```bash
# 1. 新建文章
vim _posts/2026-09-15-my-note.md

# 2. 本地看一眼（可选）
bash tools/local-preview.sh

# 3. 发布
git add -A && git commit -m "post: my note" && git push
```

## 常见坑（提前记下来）

- **仓库名不是 `<用户名>.github.io`** 时，站点会挂在子路径，必须在 `_config.yml` 里设 `baseurl: "/仓库名"`，否则样式全 404
- 改了 `_config.yml` 必须 push 触发重建，它是构建期配置，不是运行时读取
- 部署流水线里的 `actions/checkout` 要带 `fetch-depth: 0`，否则"最后修改时间"全都是构建时间

## 下一步想写的东西

- 折腾记录：工具链、环境配置这类容易忘的东西
- 读书/课程笔记
- 一些踩坑复盘

> 想开评论的话，去 [giscus.app](https://giscus.app) 生成配置，填进 `_config.yml` 的 `comments` 段即可（无需后端）。
{: .prompt-tip }
