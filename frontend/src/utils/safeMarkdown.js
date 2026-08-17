// 受控 Markdown 解析器：只识别本项目 AI 输出约定中的最小语法集合。
// 安全原则：先对每一段原始文本 HTML 转义，再基于允许的 Markdown 标记生成 HTML；
// 不接受原始 HTML、链接、图片、脚本或任意属性，供 v-html 安全使用。

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInline(text) {
  let output = escapeHtml(text);
  // 先处理代码，避免代码中的 ** 被作为强调语法解析。
  output = output.replace(/`([^`]+)`/g, "<code>$1</code>");
  output = output.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return output;
}

function isTableDivider(line) {
  const cells = line.trim().replace(/^\||\|$/g, "").split("|");
  return cells.length > 0 && cells.every((cell) => /^\s*:?-{3,}:?\s*$/.test(cell));
}

function splitTableRow(line) {
  return line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
}

function isTableRow(line) {
  return /^\s*\|?.+\|.+\|?\s*$/.test(line);
}

function flushParagraph(buffer, blocks) {
  if (!buffer.length) return;
  blocks.push(`<p>${buffer.map(renderInline).join("<br>")}</p>`);
  buffer.length = 0;
}

function flushList(list, blocks) {
  if (!list) return null;
  const items = list.items.map((item) => `<li>${renderInline(item)}</li>`).join("");
  blocks.push(`<${list.type}>${items}</${list.type}>`);
  return null;
}

/**
 * 将模型文本转换为受控 HTML。
 * 格式残缺时按普通段落降级，绝不抛出或丢失内容。
 */
export function renderSafeMarkdown(value) {
  const lines = String(value ?? "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  const paragraph = [];
  let list = null;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();
    const next = lines[index + 1] ?? "";

    // 简单 GFM 表格：标题行 + 分隔行 + 数据行。格式不完整则走普通段落。
    if (isTableRow(line) && isTableDivider(next)) {
      flushParagraph(paragraph, blocks);
      list = flushList(list, blocks);
      const headers = splitTableRow(line);
      const rows = [];
      index += 2;
      while (index < lines.length && isTableRow(lines[index]) && !isTableDivider(lines[index])) {
        rows.push(splitTableRow(lines[index]));
        index += 1;
      }
      index -= 1;
      const head = headers.map((cell) => `<th>${renderInline(cell)}</th>`).join("");
      const body = rows
        .map((row) => `<tr>${headers.map((_, i) => `<td>${renderInline(row[i] ?? "")}</td>`).join("")}</tr>`)
        .join("");
      blocks.push(`<div class="ai-table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`);
      continue;
    }

    if (!trimmed) {
      flushParagraph(paragraph, blocks);
      list = flushList(list, blocks);
      continue;
    }

    // 受控子集只输出 h1/h2；兼容旧内容的 ### 及更深层标题统一降为 h2，避免裸标记。
    const heading = /^(#{1,6})\s+(.+)$/.exec(trimmed);
    if (heading) {
      flushParagraph(paragraph, blocks);
      list = flushList(list, blocks);
      const level = heading[1].length === 1 ? 1 : 2;
      blocks.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      continue;
    }

    if (/^(---+|\*\*\*+|___+)\s*$/.test(trimmed)) {
      flushParagraph(paragraph, blocks);
      list = flushList(list, blocks);
      blocks.push("<hr>");
      continue;
    }

    const quote = /^>\s?(.*)$/.exec(trimmed);
    if (quote) {
      flushParagraph(paragraph, blocks);
      list = flushList(list, blocks);
      blocks.push(`<blockquote>${renderInline(quote[1])}</blockquote>`);
      continue;
    }

    const ordered = /^\d+[.)]\s+(.+)$/.exec(trimmed);
    const unordered = /^[-*+]\s+(.+)$/.exec(trimmed);
    if (ordered || unordered) {
      flushParagraph(paragraph, blocks);
      const type = ordered ? "ol" : "ul";
      if (list && list.type !== type) list = flushList(list, blocks);
      if (!list) list = { type, items: [] };
      list.items.push((ordered || unordered)[1]);
      continue;
    }

    list = flushList(list, blocks);
    paragraph.push(line);
  }

  flushParagraph(paragraph, blocks);
  flushList(list, blocks);
  return blocks.join("");
}

/** 复制时使用可读纯文本，而非渲染后的 HTML。 */
export function markdownToPlainText(value) {
  return String(value ?? "")
    .replace(/\r\n?/g, "\n")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^>\s?/gm, "")
    .replace(/^\s*(---+|\*\*\*+|___+)\s*$/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^\|\s*/gm, "")
    .replace(/\s*\|\s*$/gm, "")
    .replace(/\s*\|\s*/g, " | ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
