import {
  Component, Input, Output, EventEmitter, signal, computed, ViewChild, ElementRef
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Observable } from 'rxjs';
import { FileInfo } from '../../../core/models/skill.models';

@Component({
  selector: 'app-file-list',
  standalone: true,
  imports: [CommonModule],
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
  @Input() deleteFn?: (name: string) => Observable<{ deleted: string }>;
  @Input() uploadFn?: (file: File) => Observable<unknown>;

  @Output() refreshed = new EventEmitter<void>();

  dragging = signal(false);
  uploading = signal(false);
  deleting = signal<string | null>(null);

  formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  onDragOver(e: DragEvent) { e.preventDefault(); this.dragging.set(true); }
  onDragLeave() { this.dragging.set(false); }

  onDrop(e: DragEvent) {
    e.preventDefault();
    this.dragging.set(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) this.upload(file);
  }

  onFileSelected(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (file) this.upload(file);
  }

  upload(file: File) {
    if (!this.uploadFn) return;
    this.uploading.set(true);
    this.uploadFn(file).subscribe({
      next: () => { this.uploading.set(false); this.refreshed.emit(); },
      error: () => { this.uploading.set(false); },
    });
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

  delete(name: string) {
    if (!this.deleteFn) return;
    this.deleting.set(name);
    this.deleteFn(name).subscribe({
      next: () => { this.deleting.set(null); this.refreshed.emit(); },
      error: () => { this.deleting.set(null); },
    });
  }
}
