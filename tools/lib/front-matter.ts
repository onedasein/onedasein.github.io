/**
 * front matter 切分。
 *
 * 刻意手写而非引第三方：Jekyll 的规则很简单（首行 `---` 到下一个 `---`），
 * 手写能顺带保住「正文第一行在源文件里是第几行」这个信息 —— 报错要靠它定位。
 */
import { parse as parseYaml } from "yaml";

export type Split = {
  /** 故意是 unknown：调用方必须先用 schema 校验，不能直接当对象用。 */
  readonly data: unknown;
  readonly body: string;
  /** 正文第一行在源文件中的行号（1 基）。 */
  readonly bodyLine: number;
};

const DELIMITER = /^---\s*$/u;

export function splitFrontMatter(source: string): Split {
  const lines = source.split(/\r?\n/u);
  const first = lines[0];
  if (first === undefined || !DELIMITER.test(first)) {
    return { data: undefined, body: source, bodyLine: 1 };
  }

  let end = -1;
  for (let i = 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (line !== undefined && DELIMITER.test(line)) {
      end = i;
      break;
    }
  }
  if (end === -1) return { data: undefined, body: source, bodyLine: 1 };

  const yamlText = lines.slice(1, end).join("\n");
  const body = lines.slice(end + 1).join("\n");
  return { data: parseYaml(yamlText) as unknown, body, bodyLine: end + 2 };
}
