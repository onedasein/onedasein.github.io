#!/usr/bin/env bash
#
# 一次性初始化：把仓库里的占位符替换成你的真实信息。
#
# 用法:
#   bash tools/init-site.sh -u <GitHub用户名> [-n <显示名>] [-e <邮箱>] [-d <自定义域名>] [-r <项目站点仓库名>]
#
# 例（用户站点，即仓库名 <用户名>.github.io）:
#   bash tools/init-site.sh -u alice -n "爱丽丝" -e me@example.com
#
# 例（项目站点，即仓库名 blog，站点在 /blog 子路径）:
#   bash tools/init-site.sh -u alice -r blog
#
# 例（还要绑自定义域名）:
#   bash tools/init-site.sh -u alice -e me@example.com -d blog.example.com

set -euo pipefail

username=""
name=""
email=""
domain=""
repo=""

usage() {
  sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while getopts ":u:n:e:d:r:h" opt; do
  case "$opt" in
  u) username="$OPTARG" ;;
  n) name="$OPTARG" ;;
  e) email="$OPTARG" ;;
  d) domain="$OPTARG" ;;
  r) repo="$OPTARG" ;;
  h) usage 0 ;;
  *) echo "未知选项: -$OPTARG" >&2; usage 1 ;;
  esac
done

[ -n "$username" ] || { echo "❌ 必须用 -u 提供 GitHub 用户名" >&2; usage 1; }
[ -n "$name" ] || name="$username"

cd "$(dirname "$0")/.."
cfg="_config.yml"
[ -f "$cfg" ] || { echo "❌ 找不到 $cfg，请在博客仓库根目录运行" >&2; exit 1; }

site_url="https://${username}.github.io"
[ -n "$domain" ] && site_url="https://${domain}"

escape() { printf '%s' "$1" | sed -e 's/[&|\\]/\\&/g'; }

sed -i \
  -e "s|YOUR_USERNAME|$(escape "$username")|g" \
  -e "s|YOUR_NAME|$(escape "$name")|g" \
  "$cfg"
sed -i "s|you@example.com|$(escape "$email")|g" "$cfg"
sed -i "s|^url:.*|url: \"$(escape "$site_url")\"|" "$cfg"

if [ -n "$repo" ]; then
  sed -i "s|^baseurl:.*|baseurl: \"/$(escape "$repo")\"|" "$cfg"
fi
# 仓库名：优先用 -r 传入的，否则取当前目录名
repo_name="${repo:-$(basename "$(pwd)")}"
# 先处理「源码仓库」那一行（含两个 YOUR_USERNAME），再统一替换其余占位符
sed -i "s|YOUR_USERNAME/YOUR_USERNAME.github.io|$(escape "$username")/$(escape "$repo_name")|" _tabs/about.md
sed -i "s|YOUR_USERNAME|$(escape "$username")|g" _tabs/about.md
sed -i "s|YOUR_NAME|$(escape "$name")|g" _tabs/about.md
if [ -n "$email" ]; then
  sed -i "s|you@example.com|$(escape "$email")|g" _tabs/about.md
else
  # 没给邮箱就把「邮箱」这一行整行删掉，免得挂个 GitHub 链接顶着邮箱的标签
  sed -i "/<you@example\.com>/d" _tabs/about.md
fi

echo "✅ 已写入: $cfg / _tabs/about.md"
echo "   GitHub 用户名 : $username"
echo "   显示名        : $name"
if [ -n "$email" ]; then echo "   邮箱          : $email"; fi
echo "   站点 URL      : $site_url"
if [ -n "$repo" ]; then echo "   baseurl       : /$repo"; else echo "   baseurl       : （根路径，保持空）"; fi

leftover="$(grep -nE 'YOUR_USERNAME|YOUR_NAME|you@example\.com' "$cfg" _tabs/about.md || true)"
if [ -n "$leftover" ]; then
  echo
  echo "⚠️ 还有残留占位符，请手工检查："
  echo "$leftover"
fi

cat <<'NEXT'

下一步：
  1) git add -A && git commit -m "chore: init site" && git push -u origin main
  2) 打开 GitHub 仓库 → Settings → Pages → Source 选 "GitHub Actions"
  3) 等 Actions 绿勾，访问站点 URL
  4) 想开评论/统计：按 _config.yml 里 comments / analytics 的注释填
NEXT
