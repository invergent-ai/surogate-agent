import {
  Component, Input, Output, EventEmitter, ElementRef, ViewChild,
  OnChanges, SimpleChanges, OnDestroy, effect, inject, afterNextRender,
  ViewEncapsulation,
} from '@angular/core';
import { ThemeService } from '../../../core/services/theme.service';

/**
 * Lightweight CodeMirror 6 editor for Python files.
 *
 * All CodeMirror imports are lazy (dynamic import) so they are code-split
 * into a separate chunk and do not inflate the initial bundle.
 *
 * Inputs:
 *   value    — current document text (pass editedContent() from parent)
 *   readOnly — whether editing is allowed
 *
 * Outputs:
 *   changed  — emits the full document text whenever the user edits it
 */
@Component({
  selector: 'app-python-editor',
  standalone: true,
  encapsulation: ViewEncapsulation.None,
  styles: [`
    app-python-editor { display: block; height: 100%; }
    app-python-editor .cm-editor { height: 100%; font-size: 0.875rem; }
    app-python-editor .cm-scroller { overflow: auto; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
    app-python-editor .cm-focused { outline: none !important; }
  `],
  template: `<div #host style="height:100%"></div>`,
})
export class PythonEditorComponent implements OnChanges, OnDestroy {
  @Input() value = '';
  @Input() readOnly = false;
  @Output() changed = new EventEmitter<string>();

  @ViewChild('host', { static: true }) private host!: ElementRef<HTMLDivElement>;

  private readonly theme = inject(ThemeService);

  // Stored after async init
  private _view:                 any = null;
  private _themeCompartment:    any = null;
  private _readOnlyCompartment: any = null;
  private _oneDark:             any = null;
  private _EditorState:         any = null;

  constructor() {
    afterNextRender(() => void this._initEditor());

    // React to dark/light theme changes after the editor is mounted.
    effect(() => {
      const dark = this.theme.isDark();
      this._applyTheme(dark);
    });
  }

  private async _initEditor() {
    const [
      { basicSetup },
      { EditorView },
      { Compartment, EditorState },
      { python },
      { oneDark },
    ] = await Promise.all([
      import('codemirror'),
      import('@codemirror/view'),
      import('@codemirror/state'),
      import('@codemirror/lang-python'),
      import('@codemirror/theme-one-dark'),
    ]);

    this._oneDark      = oneDark;
    this._EditorState  = EditorState;
    this._themeCompartment    = new Compartment();
    this._readOnlyCompartment = new Compartment();

    const dark = this.theme.isDark();

    this._view = new EditorView({
      state: EditorState.create({
        doc: this.value,
        extensions: [
          basicSetup,
          python(),
          this._themeCompartment.of(dark ? oneDark : []),
          this._readOnlyCompartment.of(EditorState.readOnly.of(this.readOnly)),
          EditorView.updateListener.of(update => {
            if (update.docChanged) {
              this.changed.emit(update.state.doc.toString());
            }
          }),
        ],
      }),
      parent: this.host.nativeElement,
    });
  }

  private _applyTheme(dark: boolean) {
    if (!this._view || !this._themeCompartment || !this._oneDark) return;
    this._view.dispatch({
      effects: this._themeCompartment.reconfigure(dark ? this._oneDark : []),
    });
  }

  ngOnChanges(changes: SimpleChanges) {
    if (!this._view) return;

    if (changes['value']) {
      const current = this._view.state.doc.toString();
      // Only replace if content genuinely changed from outside (avoids
      // resetting caret position when the editor itself emitted the change).
      if (this.value !== current) {
        this._view.dispatch({
          changes: { from: 0, to: current.length, insert: this.value },
        });
      }
    }

    if (changes['readOnly'] && this._readOnlyCompartment && this._EditorState) {
      this._view.dispatch({
        effects: this._readOnlyCompartment.reconfigure(
          this._EditorState.readOnly.of(this.readOnly),
        ),
      });
    }
  }

  ngOnDestroy() {
    this._view?.destroy();
    this._view = null;
  }
}
