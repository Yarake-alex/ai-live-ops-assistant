import assert from "node:assert/strict";
import { markdownToPlainText, renderSafeMarkdown } from "./safeMarkdown.js";

const cases = [
  {
    name: "正常 Markdown",
    input: "# 开场\n**重点**内容\n- 第一项\n- 第二项\n---\n> 提示\n\n`code`",
    check: (html) => /<h1>开场<\/h1>/.test(html) && /<strong>重点<\/strong>/.test(html) && /<ul>/.test(html),
  },
  {
    name: "纯文本旧格式",
    input: "这是旧格式纯文本\n第二行继续说明",
    check: (html) => /<p>这是旧格式纯文本<br>第二行继续说明<\/p>/.test(html),
  },
  {
    name: "格式不完整",
    input: "#\n**未闭合\n- 列表\n### 三级标题仍可展示",
    check: (html) => html.includes("**未闭合") && /<h2>三级标题仍可展示<\/h2>/.test(html),
  },
  {
    name: "疑似 HTML",
    input: "# <img src=x onerror=alert(1)>\n<script>alert(1)</script>\n**<b>重点</b>**",
    check: (html) => html.includes("&lt;img") && html.includes("&lt;script&gt;") && !html.includes("<img ") && !html.includes("<script>"),
  },
  {
    name: "简单表格",
    input: "| 标题 | 内容 |\n|---|---|\n| A | B |",
    check: (html) => /<table>/.test(html) && /<th>标题<\/th>/.test(html) && /<td>B<\/td>/.test(html),
  },
];

for (const { name, input, check } of cases) {
  const html = renderSafeMarkdown(input);
  assert.ok(check(html), `${name} rendered unexpectedly: ${html}`);
  const copied = markdownToPlainText(input);
  assert.ok(copied, `${name} copy should remain readable plain text`);
  if (name !== "疑似 HTML") {
    assert.ok(!/<\/?\w+/.test(copied), `${name} copy should not contain generated HTML tags`);
  }
}

console.log(`${cases.length} safe Markdown cases passed`);
