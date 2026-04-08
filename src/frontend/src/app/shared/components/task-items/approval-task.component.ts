import {
  Component, Input, Output, EventEmitter, inject, signal,
  OnChanges, OnDestroy, SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TaskService } from '../../../core/services/task.service';
import { SessionsService } from '../../../core/services/sessions.service';
import { HumanTask } from '../../../core/models/task.models';
import { parseSegs, fileSegOf, Seg, FileSeg } from './task-file-refs';

@Component({
  selector: 'app-approval-task',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="flex flex-col gap-3">

      @if (descSegs.length > 0) {
        <div class="text-sm text-gray-700 dark:text-zinc-300 leading-relaxed">
          @for (seg of descSegs; track $index) {
            @if (seg.kind === 'text') {
              <span class="whitespace-pre-wrap">{{ seg.text }}</span>
            } @else {
              <span class="inline-flex items-center gap-1.5 mx-0.5 my-0.5 align-middle
                           px-2 py-0.5 rounded-md text-xs
                           bg-gray-100 dark:bg-zinc-800
                           border border-gray-200 dark:border-zinc-700">
                <svg class="w-3 h-3 text-gray-400 flex-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/>
                </svg>
                <span class="font-medium text-gray-700 dark:text-zinc-200 max-w-[160px] truncate" [title]="seg.filePath">{{ seg.basename }}</span>
                @if (seg.isImage) {
                  <button (click)="preview(seg)" class="text-brand hover:underline">preview</button>
                  <span class="text-gray-300 dark:text-zinc-600">·</span>
                }
                <button (click)="download(seg)" class="text-gray-500 dark:text-zinc-400 hover:text-gray-700 dark:hover:text-zinc-200 hover:underline">download</button>
              </span>
            }
          }
        </div>

        <!-- Inline image thumbnails -->
        @if (imageSegs.length > 0) {
          <div class="flex flex-wrap gap-2">
            @for (seg of imageSegs; track seg.fullPath) {
              <div class="relative group cursor-pointer rounded-lg overflow-hidden border border-gray-200 dark:border-zinc-700"
                   (click)="preview(seg)">
                @if (imageUrls()[seg.fullPath]) {
                  <img [src]="imageUrls()[seg.fullPath]"
                       class="max-h-48 max-w-full object-contain bg-gray-50 dark:bg-zinc-800"
                       [alt]="seg.basename" />
                } @else {
                  <div class="h-20 w-32 bg-gray-100 dark:bg-zinc-800 flex items-center justify-center text-xs text-gray-400 dark:text-zinc-500">
                    loading…
                  </div>
                }
                <div class="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                  <svg class="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                    <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                  </svg>
                </div>
              </div>
            }
          </div>
        }
      }

      <textarea
        [(ngModel)]="feedback"
        placeholder="Optional feedback…"
        rows="2"
        class="w-full text-sm rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-800 dark:text-zinc-100 placeholder-gray-400 dark:placeholder-zinc-500 px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-brand/50"
      ></textarea>

      <div class="flex gap-2">
        <button
          (click)="approve()"
          [disabled]="submitting()"
          class="flex-1 py-2 px-3 rounded-lg text-sm font-medium bg-emerald-500 hover:bg-emerald-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          @if (submitting() && lastAction === 'approve') { Approving… } @else { Approve }
        </button>
        <button
          (click)="reject()"
          [disabled]="submitting()"
          class="flex-1 py-2 px-3 rounded-lg text-sm font-medium bg-red-500 hover:bg-red-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          @if (submitting() && lastAction === 'reject') { Rejecting… } @else { Reject }
        </button>
      </div>
    </div>
  `,
})
export class ApprovalTaskComponent implements OnChanges, OnDestroy {
  @Input({ required: true }) task!: HumanTask;
  @Output() responded = new EventEmitter<void>();

  private taskSvc     = inject(TaskService);
  private sessionsSvc = inject(SessionsService);

  submitting = signal(false);
  feedback   = '';
  lastAction: 'approve' | 'reject' | null = null;

  // Parsed segments and image state
  descSegs:   Seg[]                                              = [];
  imageSegs:  FileSeg[]                                          = [];
  ctxEntries: Array<{ key: string; value: string; seg: FileSeg | null }> = [];
  imageUrls   = signal<Record<string, string>>({});
  private _blobUrls: string[] = [];

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['task'] && this.task) {
      this._clearUrls();
      this.descSegs = parseSegs(this.task.description ?? '');

      // File paths already present in the description — don't repeat in context.
      const descPaths = new Set(
        this.descSegs.filter((s): s is FileSeg => s.kind === 'file').map(s => s.fullPath)
      );

      // Keep only context entries whose file path isn't already in the description.
      // If after deduplication an entry has no remaining value to show, drop it.
      this.ctxEntries = Object.entries(this.task.context)
        .map(([key, v]) => {
          const str = String(v);
          const seg = fileSegOf(str);
          if (seg && descPaths.has(seg.fullPath)) return null; // duplicate — skip
          return { key, value: str, seg: seg ?? null };
        })
        .filter((e): e is NonNullable<typeof e> => e !== null);

      // Thumbnails strip: description images only, deduplicated by path.
      this.imageSegs = Array.from(
        new Map(
          this.descSegs
            .filter((s): s is FileSeg => s.kind === 'file' && s.isImage)
            .map(s => [s.fullPath, s])
        ).values()
      );
      this._loadPreviews();
    }
  }

  ngOnDestroy(): void { this._clearUrls(); }

  // ── File actions ───────────────────────────────────────────────────────────

  download(seg: FileSeg): void {
    this.sessionsSvc.downloadFile(seg.sessionId, seg.filePath).subscribe(blob => {
      const url = URL.createObjectURL(blob);
      const a   = Object.assign(document.createElement('a'), { href: url, download: seg.basename });
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }

  preview(seg: FileSeg): void {
    this.sessionsSvc.downloadFile(seg.sessionId, seg.filePath).subscribe(blob => {
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    });
  }

  // ── Task actions ───────────────────────────────────────────────────────────

  approve(): void { this._respond('approve', { decision: 'approved', feedback: this.feedback }); }
  reject():  void { this._respond('reject',  { decision: 'rejected', feedback: this.feedback }); }

  private _respond(action: 'approve' | 'reject', payload: object): void {
    this.lastAction = action;
    this.submitting.set(true);
    this.taskSvc.respond(this.task.id, payload).subscribe({
      next:  () => { this.submitting.set(false); this.responded.emit(); this.taskSvc.refresh(); },
      error: () => this.submitting.set(false),
    });
  }

  // ── Private helpers ────────────────────────────────────────────────────────

  private _loadPreviews(): void {
    // Collect all unique image segs from both description and context.
    const allImageSegs = Array.from(
      new Map([
        ...this.imageSegs,
        ...this.ctxEntries.flatMap(e => e.seg?.isImage ? [e.seg] : []),
      ].map(s => [s.fullPath, s])).values()
    );
    allImageSegs.forEach(seg => {
      this.sessionsSvc.downloadFile(seg.sessionId, seg.filePath).subscribe({
        next: blob => {
          const url = URL.createObjectURL(blob);
          this._blobUrls.push(url);
          this.imageUrls.update(m => ({ ...m, [seg.fullPath]: url }));
        },
        error: () => {},
      });
    });
  }

  private _clearUrls(): void {
    this._blobUrls.forEach(u => URL.revokeObjectURL(u));
    this._blobUrls = [];
    this.imageUrls.set({});
  }
}
