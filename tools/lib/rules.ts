/**
 * 规则集：每条规则都对应一个**真实踩过的坑**。
 *
 * 规则不是凭空设计的检查项 —— 每条都带 rationale，说明它编码了哪次事故。
 * 规则要能被解释，否则就是噪音。
 */
import { readdir, readFile } from "node:fs/promises";
import { basename, extname, join, relative } from "node:path";
import { parse as parseYaml } from "yaml";
import { splitFrontMatter } from "./front-matter.ts";
import { LocaleFile, PostFrontMatter, TabFrontMatter } from "./schema.ts";

export type Severity = "error" | "warning";

/**
 * 一条检查结果。
 *
 * 注意 `line` 声明为 `number | undefined` 而不是可选属性：在
 * exactOptionalPropertyTypes 下，「字段缺失」和「字段存在但值为 undefined」
 * 是两件事，显式写出来才能诚实表达「这条结果没有行号」。
 */
export type Finding = {
  readonly rule: string;
  readonly severity: Severity;
  readonly file: string;
  readonly line: number | undefined;
  readonly message: string;
};

export type RuleContext = {
  readonly root: string;
};

export type Rule = {
  readonly id: string;
  /** 这条规则编码了哪个真实事故 —— 让人知道它为什么存在。 */
  readonly rationale: string;
  readonly run: (ctx: RuleContext) => Promise<readonly Finding[]>;
};

const POST_NAME = /^(?<date>\d{4}-\d{2}-\d{2})-(?<slug>.+)\.(?:md|markdown)$/u;
const POST_EXTENSIONS = [".md", ".markdown"] as const;
const TAB_EXTENSIONS = [".md", ".markdown", ".html"] as const;

const HTTP_URL = /(?<scheme>https?):\/\/(?<host>[^\s/)>\]}"'`,]+)/gu;
/** 回环地址是 CI 里 html-proofer 显式放行的例外（见 pages-deploy.yml 的 --ignore-urls）。 */
const HTTP_ALLOWED_HOSTS = ["127.0.0.1", "0.0.0.0", "localhost"];

/** 目录里指定后缀的文件名（排序保证输出稳定）；目录不存在时返回空。 */
async function filesIn(dir: string, extensions: readonly string[]): Promise<string[]> {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw error;
  }
  return entries
    .filter((entry) => entry.isFile() && extensions.includes(extname(entry.name).toLowerCase()))
    .map((entry) => entry.name)
    .sort();
}

/** 字符下标 → 1 基行号。 */
function lineAt(source: string, index: number): number {
  let line = 1;
  const limit = Math.min(index, source.length);
  for (let i = 0; i < limit; i += 1) {
    if (source[i] === "\n") line += 1;
  }
  return line;
}

/** 找到 `key:` 出现在第几行，用于把报错钉在一行上。 */
function lineOfKey(source: string, key: string): number | undefined {
  const lines = source.split("\n");
  const pattern = new RegExp(`^\\s*${key}\\s*:`, "u");
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (line !== undefined && pattern.test(line)) return i + 1;
  }
  return undefined;
}

/**
 * 把围栏代码块与行内代码替换成等长空白，**保持行号不变**。
 *
 * 没有这一步，博客里讲解 `http://` 的代码片段会被自己的链接规则误伤 ——
 * 这是「自检工具必须先学会忽略什么」的典型例子。
 * （未处理缩进式代码块；若将来用到，在此处补即可。）
 */
export function maskCode(body: string): string {
  let inFence = false;
  return body
    .split("\n")
    .map((line) => {
      if (/^\s*(?:```|~~~)/u.test(line)) {
        inFence = !inFence;
        return "";
      }
      if (inFence) return "";
      return line.replace(/`[^`]*`/gu, (chunk) => " ".repeat(chunk.length));
    })
    .join("\n");
}

/** 文件名合规：日期后必须有 slug。 */
const postsFilename: Rule = {
  id: "posts/filename",
  rationale:
    "Jekyll 认文章的正则是 (\\d{2,4}-\\d{1,2}-\\d{1,2})-(.*)\\.[^.]+ —— 日期后必须有 slug。`2026-09-23.md` 根本不是文章，内容怎么改都不会出现在站点上。",
  run: async (ctx) => {
    const dir = join(ctx.root, "_posts");
    const found: Finding[] = [];
    for (const name of await filesIn(dir, POST_EXTENSIONS)) {
      if (POST_NAME.test(name)) continue;
      found.push({
        rule: "posts/filename",
        severity: "error",
        file: relative(ctx.root, join(dir, name)),
        line: 1,
        message: `文件名 \`${name}\` 不合法：必须形如 \`YYYY-MM-DD-<slug>.md\`（日期后要有 slug）。`,
      });
    }
    return found;
  },
};

/** front matter 的 title / date 必须能被 Jekyll 正确解析。 */
const postsFrontMatter: Rule = {
  id: "posts/front-matter",
  rationale:
    "date 的时区必须与站点一致且合法：前端写成 +8000 会让 Ruby Time.parse 抛 utc_offset out of range，Jekyll 静默回退到文件名日期 —— 时间不对却看不出来。",
  run: async (ctx) => {
    const dir = join(ctx.root, "_posts");
    const found: Finding[] = [];
    for (const name of await filesIn(dir, POST_EXTENSIONS)) {
      const file = relative(ctx.root, join(dir, name));
      const source = await readFile(join(dir, name), "utf8");
      const { data } = splitFrontMatter(source);

      if (data === undefined) {
        found.push({
          rule: "posts/front-matter",
          severity: "error",
          file,
          line: 1,
          message: "缺少 front matter：文件必须以 `---` 开头、以 `---` 结束。",
        });
        continue;
      }

      const result = PostFrontMatter.safeParse(data);
      if (result.success) continue;

      for (const issue of result.error.issues) {
        const key = typeof issue.path[0] === "string" ? issue.path[0] : undefined;
        found.push({
          rule: "posts/front-matter",
          severity: "error",
          file,
          line: key === undefined ? 1 : lineOfKey(source, key),
          message: `${key ?? "front matter"}: ${issue.message}`,
        });
      }
    }
    return found;
  },
};

/** 正文里的明文 http 链接会被 html-proofer 判死。 */
const postsHttpsLinks: Rule = {
  id: "posts/https-links",
  rationale:
    "CI 的 Test site 用 html-proofer 5，即使带 --disable-external 也会把 http:// 判为失败（is not an HTTPS link）。",
  run: async (ctx) => {
    const dir = join(ctx.root, "_posts");
    const found: Finding[] = [];
    for (const name of await filesIn(dir, POST_EXTENSIONS)) {
      const file = relative(ctx.root, join(dir, name));
      const source = await readFile(join(dir, name), "utf8");
      const { body, bodyLine } = splitFrontMatter(source);
      const masked = maskCode(body);

      for (const match of masked.matchAll(HTTP_URL)) {
        if (match.groups?.["scheme"] !== "http") continue;
        const host = match.groups["host"] ?? "";
        if (HTTP_ALLOWED_HOSTS.some((allowed) => host.startsWith(allowed))) continue;
        found.push({
          rule: "posts/https-links",
          severity: "error",
          file,
          line: lineAt(masked, match.index) + bodyLine - 1,
          message: `正文里的明文 http 链接会让 CI 失败，请改用 https：http://${host}…`,
        });
      }
    }
    return found;
  },
};

/** 每个 tab 都要在 locale 的 tabs 段里有对应键。 */
const tabsLocaleKeys: Rule = {
  id: "tabs/locale-keys",
  rationale:
    "Chirpy 的 head.html 用 `tabs[page.title | downcase]` 取页面标题；page.title 缺省时由 Jekyll 的 titleize_slug 从文件名兜底，所以键就是文件名。locale 里缺这个键，页面 <title> 会渲染为空。侧栏走的是另一条路（URL slug），两条路必须在同一个键上汇合。",
  run: async (ctx) => {
    const found: Finding[] = [];
    const localeDir = join(ctx.root, "_data", "locales");
    const locales: { file: string; tabs: Record<string, string> }[] = [];

    for (const name of await filesIn(localeDir, [".yml", ".yaml"])) {
      const file = relative(ctx.root, join(localeDir, name));
      const parsed: unknown = parseYaml(await readFile(join(localeDir, name), "utf8"));
      const result = LocaleFile.safeParse(parsed);
      if (!result.success) {
        found.push({
          rule: "tabs/locale-keys",
          severity: "error",
          file,
          line: 1,
          message: "locale 文件缺少 `tabs:` 段（约定：`tabs:` 下是 `文件名: 显示名`）。",
        });
        continue;
      }
      locales.push({ file, tabs: result.data.tabs });
    }

    const tabsDir = join(ctx.root, "_tabs");
    for (const name of await filesIn(tabsDir, TAB_EXTENSIONS)) {
      const file = relative(ctx.root, join(tabsDir, name));
      const key = basename(name, extname(name)).toLowerCase();
      const source = await readFile(join(tabsDir, name), "utf8");
      const { data } = splitFrontMatter(source);
      const parsed = TabFrontMatter.safeParse(data ?? {});
      if (!parsed.success) {
        found.push({
          rule: "tabs/locale-keys",
          severity: "error",
          file,
          line: 1,
          message: `front matter 不合法：${parsed.error.issues.map((issue) => issue.message).join("；")}`,
        });
        continue;
      }

      const title = parsed.data.title;
      if (title !== undefined && title.toLowerCase() !== key) {
        found.push({
          rule: "tabs/locale-keys",
          severity: "warning",
          file,
          line: lineOfKey(source, "title"),
          message: `title 是 "${title}"，但文件名是 ${key}：侧栏按 URL slug 取键、页面标题按 title 取键，两者不一致时必有一处错位。`,
        });
      }

      for (const locale of locales) {
        if (Object.hasOwn(locale.tabs, key)) continue;
        found.push({
          rule: "tabs/locale-keys",
          severity: "error",
          file,
          line: lineOfKey(source, "title") ?? 1,
          message: `${locale.file} 的 tabs 段缺少键 \`${key}\` → 该页 <title> 会渲染为空。`,
        });
      }
    }
    return found;
  },
};

/** 侧栏排序要确定：order 缺失或重复都会让菜单位置不可预期。 */
const tabsOrder: Rule = {
  id: "tabs/order",
  rationale:
    "_config.yml 里 collections.tabs.sort_by: order，侧栏顺序完全由它决定；缺失或重复时位置不确定。",
  run: async (ctx) => {
    const found: Finding[] = [];
    const seen = new Map<number, string>();
    const tabsDir = join(ctx.root, "_tabs");

    for (const name of await filesIn(tabsDir, TAB_EXTENSIONS)) {
      const file = relative(ctx.root, join(tabsDir, name));
      const source = await readFile(join(tabsDir, name), "utf8");
      const { data } = splitFrontMatter(source);
      const parsed = TabFrontMatter.safeParse(data ?? {});
      if (!parsed.success) continue; // 形状问题由 tabs/locale-keys 报

      const order = parsed.data.order;
      if (order === undefined) {
        found.push({
          rule: "tabs/order",
          severity: "warning",
          file,
          line: 1,
          message: "缺少 order：侧栏位置不确定，建议显式给一个正整数。",
        });
        continue;
      }

      const clash = seen.get(order);
      if (clash !== undefined) {
        found.push({
          rule: "tabs/order",
          severity: "warning",
          file,
          line: lineOfKey(source, "order"),
          message: `order: ${order} 与 ${clash} 重复。`,
        });
      } else {
        seen.set(order, file);
      }
    }
    return found;
  },
};

const ruleList = [
  postsFilename,
  postsFrontMatter,
  postsHttpsLinks,
  tabsLocaleKeys,
  tabsOrder,
] satisfies readonly Rule[];

export const rules: readonly Rule[] = ruleList;
