import {
  Component, Input, signal, computed, inject, OnChanges, SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';
import hljs from 'highlight.js/lib/core';
import langPython     from 'highlight.js/lib/languages/python';
import langJS         from 'highlight.js/lib/languages/javascript';
import langTS         from 'highlight.js/lib/languages/typescript';
import langBash       from 'highlight.js/lib/languages/bash';
import langJSON       from 'highlight.js/lib/languages/json';
import langXML        from 'highlight.js/lib/languages/xml';
import langCSS        from 'highlight.js/lib/languages/css';
import langYAML       from 'highlight.js/lib/languages/yaml';
import langSQL        from 'highlight.js/lib/languages/sql';
import langMarkdown   from 'highlight.js/lib/languages/markdown';
import langPlaintext  from 'highlight.js/lib/languages/plaintext';
import langRust       from 'highlight.js/lib/languages/rust';
import langGo         from 'highlight.js/lib/languages/go';
import langJava       from 'highlight.js/lib/languages/java';
import langCPP        from 'highlight.js/lib/languages/cpp';
import langPHP        from 'highlight.js/lib/languages/php';

hljs.registerLanguage('python',     langPython);
hljs.registerLanguage('javascript', langJS);
hljs.registerLanguage('js',         langJS);
hljs.registerLanguage('typescript', langTS);
hljs.registerLanguage('ts',         langTS);
hljs.registerLanguage('bash',       langBash);
hljs.registerLanguage('sh',         langBash);
hljs.registerLanguage('shell',      langBash);
hljs.registerLanguage('json',       langJSON);
hljs.registerLanguage('html',       langXML);
hljs.registerLanguage('xml',        langXML);
hljs.registerLanguage('css',        langCSS);
hljs.registerLanguage('yaml',       langYAML);
hljs.registerLanguage('yml',        langYAML);
hljs.registerLanguage('sql',        langSQL);
hljs.registerLanguage('markdown',   langMarkdown);
hljs.registerLanguage('md',         langMarkdown);
hljs.registerLanguage('plaintext',  langPlaintext);
hljs.registerLanguage('text',       langPlaintext);
hljs.registerLanguage('rust',       langRust);
hljs.registerLanguage('go',         langGo);
hljs.registerLanguage('java',       langJava);
hljs.registerLanguage('cpp',        langCPP);
hljs.registerLanguage('php',        langPHP);

const EXT_MAP: Record<string, string> = {
  python: 'py', javascript: 'js', js: 'js', typescript: 'ts', ts: 'ts',
  bash: 'sh', sh: 'sh', shell: 'sh', json: 'json', html: 'html', xml: 'xml',
  css: 'css', yaml: 'yml', yml: 'yml', sql: 'sql', markdown: 'md', md: 'md',
  rust: 'rs', go: 'go', java: 'java', cpp: 'cpp', c: 'c', ruby: 'rb', php: 'php',
  plaintext: 'txt', text: 'txt',
};

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function encodeCode(code: string): string {
  try { return btoa(unescape(encodeURIComponent(code))); } catch { return btoa(code); }
}

function decodeCode(b64: string): string {
  try { return decodeURIComponent(escape(atob(b64))); } catch { return atob(b64); }
}

const COPY_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
const DL_ICON   = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`;
const CHECK_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;

function buildCodeBlock(text: string, lang: string): string {
  const parts      = lang.trim().split(/\s+/);
  const language   = parts[0] || '';
  const filename   = parts.slice(1).find(p => p.includes('.')) ?? '';
  const ext        = EXT_MAP[language] ?? language ?? 'txt';
  const dlFilename = filename || (language ? `code.${ext}` : 'code.txt');
  const b64        = encodeCode(text);
  const langLabel  = filename ? `📄 ${esc(filename)}` : (language || 'text');
  const langClass  = language && hljs.getLanguage(language) ? ` language-${esc(language)}` : '';

  let highlighted: string;
  try {
    highlighted = language && hljs.getLanguage(language)
      ? hljs.highlight(text, { language }).value
      : esc(text);
  } catch { highlighted = esc(text); }

  return `<div class="md-code-block">
  <div class="md-code-header">
    <span class="md-code-lang">${langLabel}</span>
    <div class="md-code-btns">
      <button class="md-code-btn" data-action="download" data-b64="${b64}" data-filename="${esc(dlFilename)}" title="Download ${esc(dlFilename)}">
        ${DL_ICON}<span class="md-btn-label">Download</span>
      </button>
      <button class="md-code-btn" data-action="copy" data-b64="${b64}" title="Copy code">
        ${COPY_ICON}<span class="md-btn-label">Copy</span>
      </button>
    </div>
  </div>
  <pre class="md-code-pre"><code class="hljs${langClass}">${highlighted}</code></pre>
</div>`;
}

// Configure marked once at module level
let _markedReady = false;
function ensureMarked() {
  if (_markedReady) return;
  _markedReady = true;
  marked.use({
    gfm: true,
    breaks: false,
    renderer: {
      code(token: { text: string; lang?: string }) {
        return buildCodeBlock(token.text, token.lang ?? '');
      },
    },
  });
}

function renderMarkdown(text: string): string {
  ensureMarked();
  return marked.parse(text, { async: false }) as string;
}

@Component({
  selector: 'app-markdown-content',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './markdown-content.component.html',
})
export class MarkdownContentComponent implements OnChanges {
  @Input({ required: true }) text!: string;
  /** True once the streaming turn is complete — enables rendered view and toolbar. */
  @Input() finalized = true;
  /** True when this text block is followed by tool calls in the same message turn.
   *  Intermediary blocks are always rendered (no streaming cursor) and never show
   *  the Raw / Copy / Download toolbar. */
  @Input() intermediary = false;

  rawMode       = signal(false);
  copyFeedback  = signal(false);

  private sanitizer = inject(DomSanitizer);

  safeHtml = computed<SafeHtml>(() =>
    this.sanitizer.bypassSecurityTrustHtml(renderMarkdown(this.text))
  );

  ngOnChanges(changes: SimpleChanges) {
    // When a message finalizes, leave rawMode as-is (user may have toggled it)
    if (changes['text'] && !changes['finalized']) {
      // text changed during streaming — nothing extra needed
    }
  }

  toggleRaw() { this.rawMode.update(v => !v); }

  async copyAll() {
    try {
      await navigator.clipboard.writeText(this.text);
      this.copyFeedback.set(true);
      setTimeout(() => this.copyFeedback.set(false), 1500);
    } catch { /* clipboard denied */ }
  }

  downloadMd() {
    const blob = new Blob([this.text], { type: 'text/markdown;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = Object.assign(document.createElement('a'), { href: url, download: 'message.md' });
    a.click();
    URL.revokeObjectURL(url);
  }

  /** Event delegation — handles clicks on copy/download buttons inside code blocks. */
  handleClick(event: MouseEvent) {
    const btn = (event.target as Element).closest<HTMLElement>('[data-action]');
    if (!btn) return;

    const action   = btn.dataset['action'];
    const b64      = btn.dataset['b64'] ?? '';
    const code     = decodeCode(b64);
    const filename = btn.dataset['filename'] ?? 'code.txt';

    if (action === 'copy') {
      event.preventDefault();
      navigator.clipboard.writeText(code).then(() => {
        const label = btn.querySelector<HTMLElement>('.md-btn-label');
        if (!label) return;
        const orig = label.innerHTML;
        btn.innerHTML = `${CHECK_SVG}<span class="md-btn-label" style="color:#22c55e">Copied!</span>`;
        setTimeout(() => { btn.innerHTML = `${COPY_ICON}<span class="md-btn-label">${orig}</span>`; }, 1500);
      }).catch(() => {});
    }

    if (action === 'download') {
      event.preventDefault();
      const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
      const url  = URL.createObjectURL(blob);
      const a    = Object.assign(document.createElement('a'), { href: url, download: filename });
      a.click();
      URL.revokeObjectURL(url);
    }
  }
}
