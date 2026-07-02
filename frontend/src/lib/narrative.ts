/* The controller's live stdout ends with a deterministic CLITC_RESULT_V1 block
   (Plane 3). The backend stores a display-clean narrative for the final bubble,
   but the live stream carries the raw sentinel mid-flight — so any surface that
   renders accumulating controller output must hide everything from the sentinel
   onward (it is protocol, never prose). See controller_protocol.py. */

const RESULT_OPEN = "<<<CLITC_RESULT_V1";

/** Drop the result block (and any partial leading sentinel) from displayed text. */
export function stripResultSentinel(text: string): string {
  const i = text.indexOf(RESULT_OPEN);
  return (i === -1 ? text : text.slice(0, i)).trimEnd();
}
