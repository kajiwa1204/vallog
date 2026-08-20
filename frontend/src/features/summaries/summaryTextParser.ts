export type SummaryTextPart =
  | { type: "text"; value: string }
  | { type: "reference"; value: string; number: string };

const REFERENCE = /#(\d+)\b/g;

function isReferenceStart(content: string, index: number): boolean {
  if (index === 0) return true;

  const previous = content[index - 1];
  if (/[\w/]/.test(previous)) return false;

  // URLのクエリやフラグメントに含まれる #数字 は、PR/Issueの引用ではない。
  const tokenStart = Math.max(
    content.lastIndexOf(" ", index - 1),
    content.lastIndexOf("\n", index - 1),
    content.lastIndexOf("\t", index - 1),
  );
  return !content.slice(tokenStart + 1, index).includes("://");
}

/** AI本文をプレーンテキストとGitHub参照に分ける。 */
export function splitSummaryText(content: string): SummaryTextPart[] {
  const parts: SummaryTextPart[] = [];
  let cursor = 0;

  for (const match of content.matchAll(REFERENCE)) {
    const index = match.index;
    if (!isReferenceStart(content, index)) continue;

    if (cursor < index) {
      parts.push({ type: "text", value: content.slice(cursor, index) });
    }
    parts.push({
      type: "reference",
      value: match[0],
      number: match[1],
    });
    cursor = index + match[0].length;
  }

  if (cursor < content.length) {
    parts.push({ type: "text", value: content.slice(cursor) });
  }

  return parts.length > 0 ? parts : [{ type: "text", value: content }];
}
