#!/usr/bin/env bash
#
# 本机预览（http://127.0.0.1:4000）。
#
# 特点：把 Ruby gem 全部装在仓库内的 .blog-env/，不写系统目录、不需要 sudo。
# 适合无 root 权限、或 gem 系统目录只读的环境（例如受限沙箱）。
#
# 用法:
#   bash tools/local-preview.sh                # 首次自动装依赖，然后起服务
#   bash tools/local-preview.sh --build        # 只做生产构建（_site/）
#   BLOG_DEV_HOME=~/chirpy-env bash tools/local-preview.sh   # 换个位置放依赖

set -euo pipefail

cd "$(dirname "$0")/.."

DEV_HOME="${BLOG_DEV_HOME:-$PWD/.blog-env}"

# 本地默认不装 test 组：html-proofer 只在 CI 里跑，本地省掉 nokogiri/racc 的编译
export BUNDLE_WITHOUT="${BUNDLE_WITHOUT:-test}"

export HOME="$DEV_HOME/home"
export GEM_HOME="$DEV_HOME/gemhome"
# 不显式设 GEM_PATH：RubyGems 会自动用 GEM_HOME + 系统默认目录，刚好够用
export GEM_SPEC_CACHE="$DEV_HOME/gemspec"
export BUNDLE_USER_HOME="$DEV_HOME/bundle-home"
export PATH="$GEM_HOME/bin:$PATH"
mkdir -p "$HOME" "$GEM_HOME" "$GEM_SPEC_CACHE" "$BUNDLE_USER_HOME"

# 受限环境兜底：若 .blog-env 里备好了 Ruby 开发头文件，编译原生扩展也能用
if [ -d "$DEV_HOME/rubydev" ]; then
  export BLOG_RUBYDEV_DIR="$DEV_HOME/rubydev"
  export LIBRARY_PATH="$DEV_HOME/rubydev/usr/lib/x86_64-linux-gnu:${LIBRARY_PATH:-}"
  [ -f "$DEV_HOME/hdr.rb" ] && export RUBYOPT="-r$DEV_HOME/hdr.rb"
fi

# 预检：本机 Ruby 是否带开发头文件（缺了的话带 C 扩展的 gem 编不出来）
ruby_hdr_dir="$(ruby -rrbconfig -e 'print RbConfig::CONFIG["rubyhdrdir"]' 2>/dev/null || true)"
if [ ! -d "$DEV_HOME/rubydev" ] && [ -n "$ruby_hdr_dir" ] &&
  [ ! -f "$ruby_hdr_dir/ruby.h" ] && [ ! -f "$ruby_hdr_dir/ruby/ruby.h" ]; then
  cat <<'EOF'
⚠️  本机 Ruby 没有开发头文件（ruby-dev / ruby-devel）：
    json、bigdecimal、eventmachine、http_parser.rb 这些带 C 扩展的 gem 会编译失败。
    三种解法：
      1) Debian/Ubuntu:  sudo apt install ruby-dev build-essential
      2) 用 Docker 跑：  docker run --rm -v "$PWD":/srv/jekyll -p 4000:4000 jekyll/jekyll jekyll serve
      3) 跳过本地预览：  push 后看 GitHub Actions 的构建（CI 环境完整，部署不受影响）

    下面仍会尝试安装，预计停在编译那一步……
EOF
fi

if ! command -v bundle >/dev/null 2>&1; then
  echo ">>> 安装 bundler 到 $GEM_HOME"
  gem install bundler --no-document
fi

if ! bundle check >/dev/null 2>&1; then
  echo ">>> 安装 Gemfile 里的依赖（首次较慢，约几十 MB）"
  bundle install --jobs 4
fi

if [ "${1:-}" = "--build" ]; then
  echo ">>> 生产构建"
  rm -rf _site
  JEKYLL_ENV=production bundle exec jekyll build -d _site
  echo "✅ 构建通过：_site/"
  echo "   （html-proofer 的外链/死链检查只在 GitHub Actions 里跑）"
else
  echo ">>> 启动 Jekyll（Ctrl-C 退出）→ http://127.0.0.1:4000"
  bundle exec jekyll serve --livereload --host 127.0.0.1 --port 4000
fi
