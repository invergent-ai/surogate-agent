/**
 * Utilities for detecting file-path references inside task descriptions / context
 * values and providing typed segments for template rendering.
 *
 * Matches paths of the form:
 *   [optional-prefix/]sessions/<session-id>/<filename.ext>
 *
 * Examples:
 *   /data/sessions/abc123/chart.png
 *   sessions/abc123/subdir/report.html
 */

// Module-level regex — reset lastIndex before each use.
const _FILE_PATH_RE =
  /((?:[^\s"'`()\[\],<>]*\/)?sessions\/([a-zA-Z0-9_-]{8,})\/([\w./-]+\.[a-zA-Z0-9]{1,10}))/g;

export const IMAGE_EXTS = new Set([
  'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico',
]);

export interface TextSeg { kind: 'text'; text: string; }
export interface FileSeg {
  kind: 'file';
  /** Full matched path string (used as stable key). */
  fullPath: string;
  sessionId: string;
  /** Path relative to session workspace — passed to downloadFile(). */
  filePath: string;
  /** Last component of filePath (display name). */
  basename: string;
  isImage: boolean;
}
export type Seg = TextSeg | FileSeg;

/** Split a text string into alternating text / file-ref segments. */
export function parseSegs(text: string): Seg[] {
  const segs: Seg[] = [];
  let last = 0;
  _FILE_PATH_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = _FILE_PATH_RE.exec(text)) !== null) {
    if (m.index > last) segs.push({ kind: 'text', text: text.slice(last, m.index) });
    const fp = m[3];
    segs.push({
      kind: 'file',
      fullPath: m[1],
      sessionId: m[2],
      filePath: fp,
      basename: fp.split('/').pop() ?? fp,
      isImage: IMAGE_EXTS.has((fp.split('.').pop() ?? '').toLowerCase()),
    });
    last = m.index + m[0].length;
  }
  if (last < text.length) segs.push({ kind: 'text', text: text.slice(last) });
  return segs;
}

/** Return the FileSeg for a plain value string, or null if it's not a file path. */
export function fileSegOf(value: string): FileSeg | null {
  const segs = parseSegs(value);
  return (segs.find((s): s is FileSeg => s.kind === 'file')) ?? null;
}
