import {
  Component, Input, Output, EventEmitter, inject, signal,
  OnChanges, OnDestroy, SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { TaskService } from '../../../core/services/task.service';
import { HumanTask } from '../../../core/models/task.models';
import { parseSegs, Seg } from './task-file-refs';

@Component({
  selector: 'app-file-request-task',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="flex flex-col gap-3">

      @if (descSegs.length > 0) {
        <div class="text-sm text-gray-700 dark:text-zinc-300 leading-relaxed">
          @for (seg of descSegs; track $index) {
            @if (seg.kind === 'text') {
              <span class="whitespace-pre-wrap">{{ seg.text }}</span>
            }
          }
        </div>
      }

      @if (ctxEntries.length > 0) {
        <div class="bg-gray-50 dark:bg-zinc-800 rounded-lg p-3 flex flex-col gap-2">
          @for (entry of ctxEntries; track entry.key) {
            <div class="flex flex-col gap-1 text-xs">
              <span class="font-medium text-gray-500 dark:text-zinc-400">{{ entry.key }}</span>
              <span class="text-gray-700 dark:text-zinc-300">{{ entry.value }}</span>
            </div>
          }
        </div>
      }

      <!-- Drop zone / file picker -->
      <div
        [ngClass]="isDragging()
          ? 'relative rounded-xl border-2 border-dashed transition-colors border-violet-500 bg-violet-50 dark:bg-violet-950/20'
          : 'relative rounded-xl border-2 border-dashed transition-colors border-violet-300 dark:border-violet-700'"
        (dragover)="onDragOver($event)"
        (dragleave)="isDragging.set(false)"
        (drop)="onDrop($event)"
      >
        <input
          #fileInput
          type="file"
          multiple
          class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          (change)="onFileChange($event)"
        />
        <div class="flex flex-col items-center gap-1.5 py-5 px-4 pointer-events-none">
          <svg class="w-7 h-7 text-violet-400 dark:text-violet-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
          </svg>
          <p class="text-xs text-gray-500 dark:text-zinc-400">
            <span class="font-medium text-violet-600 dark:text-violet-400">Click to browse</span>
            &nbsp;or drag files here
          </p>
        </div>
      </div>

      <!-- Selected file list -->
      @if (selectedFiles().length > 0) {
        <ul class="flex flex-col gap-1.5">
          @for (f of selectedFiles(); track f.name) {
            <li class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-gray-50 dark:bg-zinc-800 text-xs">
              <svg class="w-3.5 h-3.5 flex-none text-violet-400 dark:text-violet-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/>
              </svg>
              <span class="flex-1 truncate font-medium text-gray-700 dark:text-zinc-200">{{ f.name }}</span>
              <span class="flex-none text-gray-400 dark:text-zinc-500">{{ formatSize(f.size) }}</span>
              <button
                (click)="removeFile(f)"
                class="flex-none text-gray-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400 transition-colors"
                title="Remove"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </li>
          }
        </ul>
      }

      <button
        (click)="submit()"
        [disabled]="submitting() || selectedFiles().length === 0"
        class="w-full py-2 px-3 rounded-lg text-sm font-medium bg-violet-500 hover:bg-violet-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {{ submitting() ? 'Uploading…' : 'Send ' + (selectedFiles().length > 0 ? selectedFiles().length + ' file' + (selectedFiles().length > 1 ? 's' : '') : 'files') }}
      </button>

    </div>
  `,
})
export class FileRequestTaskComponent implements OnChanges, OnDestroy {
  @Input({ required: true }) task!: HumanTask;
  @Output() responded = new EventEmitter<void>();

  private taskSvc = inject(TaskService);

  submitting    = signal(false);
  isDragging    = signal(false);
  selectedFiles = signal<File[]>([]);

  descSegs:   Seg[]                                   = [];
  ctxEntries: Array<{ key: string; value: string }>   = [];

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['task'] && this.task) {
      this.descSegs  = parseSegs(this.task.description ?? '');
      this.ctxEntries = Object.entries(this.task.context).map(([key, v]) => ({
        key,
        value: String(v),
      }));
      this.selectedFiles.set([]);
    }
  }

  ngOnDestroy(): void {}

  // ── Drag-and-drop ──────────────────────────────────────────────────────────

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(true);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(false);
    const files = Array.from(event.dataTransfer?.files ?? []);
    this._addFiles(files);
  }

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    this._addFiles(files);
    input.value = '';
  }

  private _addFiles(files: File[]): void {
    this.selectedFiles.update(existing => {
      const names = new Set(existing.map(f => f.name));
      return [...existing, ...files.filter(f => !names.has(f.name))];
    });
  }

  removeFile(file: File): void {
    this.selectedFiles.update(list => list.filter(f => f !== file));
  }

  // ── Submit ─────────────────────────────────────────────────────────────────

  submit(): void {
    const files = this.selectedFiles();
    if (!files.length) return;
    this.submitting.set(true);
    this.taskSvc.uploadTaskFiles(this.task.id, files).subscribe({
      next:  () => { this.submitting.set(false); this.responded.emit(); this.taskSvc.refresh(); },
      error: () => this.submitting.set(false),
    });
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  formatSize(bytes: number): string {
    if (bytes < 1024)        return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
}
