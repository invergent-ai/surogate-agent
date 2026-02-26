import {
  Component, Input, Output, EventEmitter,
  signal, OnChanges, OnDestroy, inject
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml, SafeUrl, SafeResourceUrl } from '@angular/platform-browser';
import { FullscreenService } from '../../../core/services/fullscreen.service';

type ViewMode = 'text' | 'image' | 'pdf' | 'docx' | 'unsupported';

const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif']);

@Component({
  selector: 'app-file-viewer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './file-viewer.component.html',
})
export class FileViewerComponent implements OnChanges, OnDestroy {
  @Input() content = '';
  @Input() blob?: Blob;
  @Input() fileName = '';
  @Input() readOnly = false;
  @Output() saved = new EventEmitter<string>();

  private readonly fullscreenSvc = inject(FullscreenService);
  private readonly sanitizer     = inject(DomSanitizer);

  editedContent = signal('');
  dirty         = signal(false);
  fullscreen    = signal(false);

  viewMode    = signal<ViewMode>('text');
  safeImgUrl  = signal<SafeUrl | null>(null);
  safePdfUrl  = signal<SafeResourceUrl | null>(null);
  safeDocHtml = signal<SafeHtml | null>(null);
  docLoading  = signal(false);

  private _objectUrl = '';

  ngOnChanges() {
    this._revokeUrl();
    if (this.blob) {
      this._initBlob();
    } else {
      this.viewMode.set('text');
      this.editedContent.set(this.content);
      this.dirty.set(false);
    }
  }

  private _ext(): string {
    return this.fileName.split('.').pop()?.toLowerCase() ?? '';
  }

  private _initBlob() {
    const ext = this._ext();
    if (IMAGE_EXTS.has(ext)) {
      this.viewMode.set('image');
      this._objectUrl = URL.createObjectURL(this.blob!);
      this.safeImgUrl.set(this.sanitizer.bypassSecurityTrustUrl(this._objectUrl));
    } else if (ext === 'pdf') {
      this.viewMode.set('pdf');
      this._objectUrl = URL.createObjectURL(this.blob!);
      this.safePdfUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(this._objectUrl));
    } else if (ext === 'docx') {
      this.viewMode.set('docx');
      this._renderDocx();
    } else {
      this.viewMode.set('unsupported');
    }
  }

  private async _renderDocx() {
    this.docLoading.set(true);
    this.safeDocHtml.set(null);
    try {
      const mammoth    = await import('mammoth');
      const arrayBuffer = await this.blob!.arrayBuffer();
      const result     = await mammoth.convertToHtml({ arrayBuffer });
      this.safeDocHtml.set(this.sanitizer.bypassSecurityTrustHtml(result.value));
    } catch {
      this.safeDocHtml.set(null);
    } finally {
      this.docLoading.set(false);
    }
  }

  private _revokeUrl() {
    if (this._objectUrl) {
      URL.revokeObjectURL(this._objectUrl);
      this._objectUrl = '';
    }
  }

  ngOnDestroy() {
    this._revokeUrl();
    if (this.fullscreen()) this.fullscreenSvc.close();
  }

  onInput(value: string) {
    this.editedContent.set(value);
    this.dirty.set(value !== this.content);
  }

  save() {
    this.saved.emit(this.editedContent());
    this.dirty.set(false);
  }

  reset() {
    this.editedContent.set(this.content);
    this.dirty.set(false);
  }

  openFullscreen() {
    this.fullscreen.set(true);
    this.fullscreenSvc.open();
  }

  closeFullscreen() {
    this.fullscreen.set(false);
    this.fullscreenSvc.close();
  }

  onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') this.closeFullscreen();
  }
}
