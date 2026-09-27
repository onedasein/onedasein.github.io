/**
 * 内容 schema —— 本工具的唯一事实源。
 *
 * 设计要点：先用 zod 描述「什么算合法内容」，再用 z.infer 从 schema 推导类型，
 * 而不是手写 interface 再靠人工保持一致。这样运行时校验与静态类型不可能打架。
 */
import { z } from "zod";

/** 站点时区，对应 _config.yml 的 `timezone: Asia/Shanghai`。 */
export const SITE_OFFSET = "+0800" as const;

/**
 * `YYYY-MM-DD HH:mm:ss ±HHMM` 的**形状**。
 *
 * `[+-]\d{4}` 只管形状：`+8000` 形状完全合法，但它是让 Ruby `Time.parse` 抛
 * `utc_offset out of range` 的非法偏移。所以「范围」与「站点时区一致性」交给
 * 下面的 superRefine —— 这正是形状与语义的分界。
 */
const DATE_SHAPE =
  /^(?<year>\d{4})-(?<month>\d{2})-(?<day>\d{2})[ T](?<hour>\d{2}):(?<minute>\d{2}):(?<second>\d{2})\s*(?<sign>[+-])(?<offsetHour>\d{2})(?<offsetMinute>\d{2})$/u;

export const PostDate = z
  .string()
  .regex(DATE_SHAPE, "date 必须形如 `YYYY-MM-DD HH:mm:ss ±HHMM`")
  .superRefine((value, ctx) => {
    const groups = DATE_SHAPE.exec(value)?.groups;
    if (groups === undefined) return; // 形状错误已由上一条 regex 报出

    const range = (key: string, min: number, max: number): void => {
      const raw = groups[key];
      const parsed = raw === undefined ? Number.NaN : Number.parseInt(raw, 10);
      if (Number.isNaN(parsed) || parsed < min || parsed > max) {
        ctx.addIssue({
          code: "custom",
          message: `date 的 ${key} 越界：${raw ?? "?"}（合法范围 ${min}–${max}）`,
        });
      }
    };

    range("month", 1, 12);
    range("day", 1, 31);
    range("hour", 0, 23);
    range("minute", 0, 59);
    range("second", 0, 59);

    // 偏移只报一条：`+8000`（小时越界，本身非法）与 `+0900`（合法但不是站点时区）
    // 是两类问题，分开报会让同一处改动产出两条噪音，所以按实际情况给对应说法。
    const offset = `${groups["sign"] ?? ""}${groups["offsetHour"] ?? ""}${groups["offsetMinute"] ?? ""}`;
    if (offset !== SITE_OFFSET) {
      const offsetHour = Number.parseInt(groups["offsetHour"] ?? "", 10);
      const offsetMinute = Number.parseInt(groups["offsetMinute"] ?? "", 10);
      const illegal = !(offsetHour >= 0 && offsetHour <= 23 && offsetMinute >= 0 && offsetMinute <= 59);
      ctx.addIssue({
        code: "custom",
        message: illegal
          ? `date 的时区偏移 ${offset} 是非法值（小时须 0–23、分钟须 0–59）：Ruby 的 Time.parse 会抛 utc_offset out of range，Jekyll 随即静默回退到文件名日期。站点要求 ${SITE_OFFSET}。`
          : `date 的时区应为 ${SITE_OFFSET}（站点 timezone: Asia/Shanghai），实际为 ${offset}，会让日期与预期不一致。`,
      });
    }
  });

/** `_posts/*.md` 的 front matter（只约束必要项，其余键放行）。 */
export const PostFrontMatter = z.object({
  title: z.string().min(1, "title 不能为空"),
  date: PostDate,
});
export type PostFrontMatter = z.infer<typeof PostFrontMatter>;

/**
 * `_tabs/*` 的 front matter。
 *
 * `title` 是可选的：Jekyll 会给 collection 文档兜底
 * （jekyll/document.rb: `data["title"] ||= Utils.titleize_slug(slug)`），
 * 所以不写 title 时页面标题来自文件名。而一旦显式写了，它就会参与
 * `tabs[page.title | downcase]` 查表 —— 见 rules.ts 的 tabs/locale-keys。
 */
export const TabFrontMatter = z.object({
  title: z.string().min(1, "title 一旦写了就不能为空").optional(),
  icon: z.string().optional(),
  order: z.number().int().positive().optional(),
});
export type TabFrontMatter = z.infer<typeof TabFrontMatter>;

/** `_data/locales/*.yml`，只关心 tabs 段（约定：`文件名: 显示名`）。 */
export const LocaleFile = z.object({
  tabs: z.record(z.string(), z.string()),
});
export type LocaleFile = z.infer<typeof LocaleFile>;
