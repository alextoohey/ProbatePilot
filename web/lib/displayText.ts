const EMOJI_PATTERN = new RegExp("\\p{Extended_Pictographic}|\\p{Emoji_Presentation}", "gu");

/** Normalize agent and estate text before showing it in the dashboard UI. */
export function cleanDashboardText(value: string): string {
  return value
    .replace(/\s*—\s*/g, " - ")
    .replace(EMOJI_PATTERN, "")
    .replace(/[\u200D\uFE0E\uFE0F]/g, "")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}
