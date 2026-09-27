#!/usr/bin/env node
/**
 * 博客内容自检 CLI。
 *
 *   node tools/check-content.ts [--root <目录>] [--json] [--explain]
 *
 * 退出码：有 error → 1；只有 warning 或全绿 → 0；自身执行失败 → 2。
 */
import { resolve } from "node:path";
import { rules } from "./lib/rules.ts";
import type { Finding, RuleContext, Severity } from "./lib/rules.ts";

/**
 * 允许 `| head`、`| grep -q` 这类会提前关闭管道的用法：
 * 不接这个 error 事件，Node 会因 EPIPE 抛未处理错误并打印一大段栈。
 */
process.stdout.on("error", (error: Error) => {
  if ((error as NodeJS.ErrnoException).code === "EPIPE") process.exit(0);
  throw error;
});

type CliOptions = {
  readonly root: string;
  readonly json: boolean;
  readonly explain: boolean;
  readonly help: boolean;
};

const USAGE = `用法：node tools/check-content.ts [选项]

  --root <目录>   要检查的博客根目录（默认：本文件的上一级）
  --json          以 JSON 输出，便于其他工具消费
  --explain       先列出每条规则及其存在理由
  -h, --help      显示本帮助
`;

function parseArgs(argv: readonly string[]): CliOptions {
  let root = resolve(import.meta.dirname, "..");
  let json = false;
  let explain = false;
  let help = false;

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case "--json":
        json = true;
        break;
      case "--explain":
        explain = true;
        break;
      case "-h":
      case "--help":
        help = true;
        break;
      case "--root": {
        const value = argv[i + 1];
        if (value === undefined) throw new Error("--root 需要一个目录参数");
        root = resolve(value);
        i += 1;
        break;
      }
      default:
        throw new Error(`未知参数：${String(arg)}`);
    }
  }
  return { root, json, explain, help };
}

/** 联合类型的穷尽检查：漏掉一个分支时，这里会变成编译错误。 */
function assertNever(value: never): never {
  throw new Error(`未处理的联合分支：${String(value)}`);
}

function severityLabel(severity: Severity): string {
  switch (severity) {
    case "error":
      return "ERROR";
    case "warning":
      return "WARN ";
    default:
      return assertNever(severity);
  }
}

function renderExplain(): string {
  const lines = ["规则清单：", ""];
  for (const rule of rules) {
    lines.push(`  ${rule.id}`);
    lines.push(`      ${rule.rationale}`);
  }
  lines.push("");
  return lines.join("\n");
}

function renderText(root: string, findings: readonly Finding[]): string {
  const errors = findings.filter((finding) => finding.severity === "error").length;
  const warnings = findings.length - errors;
  const lines = [`内容自检 · ${root}`, ""];

  if (findings.length === 0) {
    lines.push("全部通过，没有发现问题。");
  } else {
    for (const finding of findings) {
      const where = finding.line === undefined ? finding.file : `${finding.file}:${finding.line}`;
      lines.push(`${severityLabel(finding.severity)} [${finding.rule}] ${where}`);
      lines.push(`      ${finding.message}`);
    }
  }

  lines.push("", `${rules.length} 条规则 · ${errors} 个错误 · ${warnings} 个警告`);
  return `${lines.join("\n")}\n`;
}

async function main(): Promise<number> {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    process.stdout.write(USAGE);
    return 0;
  }

  if (options.explain) process.stdout.write(renderExplain());

  const context: RuleContext = { root: options.root };
  const findings: Finding[] = [];
  for (const rule of rules) {
    findings.push(...(await rule.run(context)));
  }
  findings.sort((left, right) => {
    if (left.file !== right.file) return left.file < right.file ? -1 : 1;
    return (left.line ?? 0) - (right.line ?? 0);
  });

  if (options.json) {
    process.stdout.write(`${JSON.stringify({ root: options.root, findings }, null, 2)}\n`);
  } else {
    process.stdout.write(renderText(options.root, findings));
  }

  return findings.some((finding) => finding.severity === "error") ? 1 : 0;
}

try {
  process.exitCode = await main();
} catch (error) {
  const detail = error instanceof Error ? error.message : String(error);
  process.stderr.write(`内容自检执行失败：${detail}\n`);
  process.exitCode = 2;
}
