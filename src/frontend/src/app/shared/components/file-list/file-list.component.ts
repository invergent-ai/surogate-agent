import {
  Component, Input, Output, EventEmitter, signal, ViewChild, ElementRef, inject
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Observable } from 'rxjs';
import { FileInfo } from '../../../core/models/skill.models';
import { FileViewerComponent } from '../file-viewer/file-viewer.component';
import { ConfirmDialogService } from '../../../core/services/confirm-dialog.service';

const TEXT_EXTENSIONS = new Set([
  'txt', 'md', 'markdown', 'csv', 'tsv', 'json', 'yaml', 'yml',
  'xml', 'html', 'htm', 'css', 'js', 'ts', 'py', 'sh', 'bash',
  'toml', 'ini', 'conf', 'config', 'log', 'sql', 'env', 'r',
  'java', 'c', 'cpp', 'h', 'rs', 'go', 'rb', 'php', 'tex',
]);

@Component({
  selector: 'app-file-list',
  standalone: true,
  imports: [CommonModule, FileViewerComponent],
  templateUrl: './file-list.component.html',
})
export class FileListComponent {
  @ViewChild('fileInput') fileInputRef!: ElementRef<HTMLInputElement>;

  @Input() title = 'Files';
  @Input() emptyMessage = 'No files yet';
  @Input() allowUpload = true;
  @Input() allowDelete = true;
  @Input() files: FileInfo[] = [];

  @Input() downloadFn?: (name: string) => Observable<Blob>;
  @Input() deleteFn?:  (name: string) => Observable<{ deleted: string }>;
  @Input() uploadFn?:  (file: File) => Observable<unknown>;
  @Input() viewFn?:    (name: string) => Observable<string>;
  @Input() saveFn?:    (name: string, content: string) => Observable<unknown>;

  @Output() refreshed   = new EventEmitter<void>();
  @Output() fileOpened  = new EventEmitter<void>();

  private confirmSvc = inject(ConfirmDialogService);

  dragging    = signal(false);
  uploading   = signal(false);
  deleting    = signal<string | null>(null);
  loadingView = signal(false);
  saving      = signal(false);

  openedFile = signal<{ name: string; content: string } | null>(null);

  isTextFile(name: string): boolean {
    const ext = name.split('.').pop()?.toLowerCase() ?? '';
    return TEXT_EXTENSIONS.has(ext);
  }

  canView(name: string): boolean {
    return !!this.viewFn && this.isTextFile(name);
  }

  formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  onDragOver(e: DragEvent)  { e.preventDefault(); this.dragging.set(true); }
  onDragLeave()              { this.dragging.set(false); }

  onDrop(e: DragEvent) {
    e.preventDefault();
    this.dragging.set(false);
    const files = e.dataTransfer?.files;
    if (files?.length) this.uploadFiles(Array.from(files));
  }

  onFileSelected(e: Event) {
    const input = e.target as HTMLInputElement;
    const files = input.files;
    if (files?.length) this.uploadFiles(Array.from(files));
    input.value = '';
  }

  onFileNameClick(name: string) {
    if (this.canView(name)) this.openView(name);
  }

  uploadFiles(files: File[]) {
    if (!this.uploadFn || files.length === 0) return;
    this.uploading.set(true);
    let pending = files.length;
    const done = () => { if (--pending === 0) { this.uploading.set(false); this.refreshed.emit(); } };
    for (const file of files) {
      this.uploadFn(file).subscribe({ next: done, error: done });
    }
  }

  download(name: string) {
    if (!this.downloadFn) return;
    this.downloadFn(name).subscribe(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = name; a.click();
      URL.revokeObjectURL(url);
    });
  }

  openView(name: string) {
    if (!this.viewFn) return;
    this.loadingView.set(true);
    this.viewFn(name).subscribe({
      next: content => {
        this.openedFile.set({ name, content });
        this.loadingView.set(false);
        this.fileOpened.emit();
      },
      error: () => { this.loadingView.set(false); },
    });
  }

  closeView() { this.openedFile.set(null); }

  onFileSaved(content: string) {
    const file = this.openedFile();
    if (!file || !this.saveFn) return;
    this.saving.set(true);
    this.saveFn(file.name, content).subscribe({
      next: () => {
        this.saving.set(false);
        // Update cached content so FileViewerComponent resets its dirty state
        this.openedFile.set({ ...file, content });
        this.refreshed.emit();
      },
      error: () => { this.saving.set(false); },
    });
  }

  async delete(name: string) {
    if (!this.deleteFn) return;
    const ok = await this.confirmSvc.confirm(
      `Delete "${name}"? This cannot be undone.`,
      { title: 'Delete file' },
    );
    if (!ok) return;
    this.deleting.set(name);
    this.deleteFn(name).subscribe({
      next:  () => {
        this.deleting.set(null);
        if (this.openedFile()?.name === name) this.openedFile.set(null);
        this.refreshed.emit();
      },
      error: () => { this.deleting.set(null); },
    });
  }
}
