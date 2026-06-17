/* Pillar 3 — readable presentation. Strip ANSI escape sequences (colors, cursor
   moves, OSC titles) from text rendered as PROSE (log/stdout/stderr views). Live
   terminal panes use xterm and keep their ANSI; this is only for the normalized
   text views where raw escapes would otherwise be unreadable noise.

   Pattern is the canonical ansi-regex form (CSI/SGR + OSC), written with unicode
   escapes so the source contains no raw control bytes. */
const ANSI_PATTERN =
  "[\\u001B\\u009B][[\\]()#;?]*(?:(?:(?:;[-a-zA-Z\\d/#&.:=?%@~_]+)*|[a-zA-Z\\d]+(?:;[-a-zA-Z\\d/#&.:=?%@~_]*)*)?\\u0007|(?:\\d{1,4}(?:;\\d{0,4})*)?[\\dA-PR-TZcf-ntqry=><~])";

export function stripAnsi(text: string | null | undefined): string {
  if (!text) return "";
  return text.replace(new RegExp(ANSI_PATTERN, "g"), "");
}

export function hasAnsi(text: string | null | undefined): boolean {
  if (!text) return false;
  return new RegExp(ANSI_PATTERN).test(text);
}
