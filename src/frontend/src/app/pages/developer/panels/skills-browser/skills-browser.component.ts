import {
  Component, Output, EventEmitter, signal, OnInit, inject, ViewChild, ElementRef, HostListener
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ConfirmDialogService } from '../../../../core/services/confirm-dialog.service';
import { SkillsService } from '../../../../core/services/skills.service';
import { SessionsService } from '../../../../core/services/sessions.service';
import { ToastService } from '../../../../core/services/toast.service';
import {
  FileInfo, SkillListItem, SkillResponse, ValidationResult
} from '../../../../core/models/skill.models';
import { HumanTask } from '../../../../core/models/task.models';
import { ValidationBadgeComponent } from '../../../../shared/components/validation-badge/validation-badge.component';
import { FileListComponent } from '../../../../shared/components/file-list/file-list.component';
import { FileViewerComponent } from '../../../../shared/components/file-viewer/file-viewer.component';

@Component({
  selector: 'app-skills-browser',
  standalone: true,
  imports: [CommonModule, FormsModule, ValidationBadgeComponent, FileListComponent, FileViewerComponent],
  templateUrl: './skills-browser.component.html',
})
export class SkillsBrowserComponent implements OnInit {
  @Output() skillSelected    = new EventEmitter<string>();
  @Output() skillDeleted     = new EventEmitter<string>();
  @Output() fileOpened       = new EventEmitter<void>();
  @Output() detailClosed     = new EventEmitter<void>();
  @Output() skillsLoaded     = new EventEmitter<string[]>();
  @Output() historyCleared   = new EventEmitter<void>();
  /** Emitted when a form chip is clicked. Null = close the preview. */
  @Output() formPreviewTask  = new EventEmitter<HumanTask | null>();

  skills = signal<SkillListItem[]>([]);
  filter = signal('');
  selectedSkill = signal<SkillResponse | null>(null);
  helperFiles = signal<FileInfo[]>([]);
  validation = signal<ValidationResult | null>(null);
  validating = signal(false);
  loading = signal(false);
  saving = signal(false);
  clearingHistory = signal(false);
  exporting = signal(false);
  importing = signal(false);

  @ViewChild('importInput') importInputRef!: ElementRef<HTMLInputElement>;
  @ViewChild(FileListComponent) private _fileList?: FileListComponent;

  closeOpenFile(): void { this._fileList?.closeView(); }

  /** Height (px) of the skill-detail pane; adjusted by dragging the separator. */
  detailHeightPx = signal<number>(280);
  private _dragStartY = 0;
  private _dragStartH = 0;

  filteredSkills = () => {
    const q = this.filter().toLowerCase();
    return this.skills().filter(s =>
      !q || s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)
    );
  };

  private confirmSvc   = inject(ConfirmDialogService);
  private sessionsSvc  = inject(SessionsService);
  private toast        = inject(ToastService);

  constructor(private skillsService: SkillsService) {}

  ngOnInit() { this.loadSkills(); }

  loadSkills(silent = false) {
    if (!silent) {
      this.deselect();
      this.detailClosed.emit();
    }
    this.skillsService.list('developer').subscribe(list => {
      this.skills.set(list);
      this.skillsLoaded.emit(list.map(s => s.name));
    });
  }

  selectSkill(name: string) {
    if (this.selectedSkill()?.name === name) {
      this.deselect();
      this.skillSelected.emit(name);
      return;
    }

    this.skillSelected.emit(name);
    this.loading.set(true);
    this.validation.set(null);
    this.detailHeightPx.set(700);
    this.skillsService.get(name).subscribe(sk => {
      this.selectedSkill.set(sk);
      this.helperFiles.set(sk.helper_files);
      this.loading.set(false);
    });
  }

  validate() {
    const sk = this.selectedSkill();
    if (!sk) return;
    this.validating.set(true);
    this.skillsService.validate(sk.name).subscribe(r => {
      this.validation.set(r);
      this.validating.set(false);
    });
  }

  saveSkillMd(content: string) {
    const sk = this.selectedSkill();
    if (!sk) return;
    this.saving.set(true);
    // Re-upload SKILL.md as a file to update it
    const blob = new Blob([content], { type: 'text/markdown' });
    const file = new File([blob], 'SKILL.md', { type: 'text/markdown' });
    this.skillsService.uploadFile(sk.name, file, true).subscribe({
      next: () => {
        this.saving.set(false);
        this.selectSkill(sk.name);
      },
      error: () => this.saving.set(false),
    });
  }

  refreshFiles() {
    const sk = this.selectedSkill();
    if (!sk) return;
    this.skillsService.listFiles(sk.name).subscribe(files => this.helperFiles.set(files));
  }

  async deleteSkill(name: string) {
    const ok = await this.confirmSvc.confirm(
      `Delete skill "${name}"? This cannot be undone.`,
      { title: 'Delete skill' },
    );
    if (!ok) return;
    this.skillsService.delete(name).subscribe(() => {
      if (this.selectedSkill()?.name === name) this.selectedSkill.set(null);
      this.loadSkills();
      this.skillDeleted.emit(name);
    });
  }

  async clearHistory(name: string) {
    const ok = await this.confirmSvc.confirm(
      `Clear the stored conversation history for "${name}"?\n\nThe LLM context for this skill will reset — the next message starts completely fresh. Workspace files are not affected.`,
      { title: 'Clear chat history', actionLabel: 'Clear' },
    );
    if (!ok) return;
    this.clearingHistory.set(true);
    this.sessionsSvc.clearHistory(`dev:${name}`).subscribe({
      next: () => {
        this.clearingHistory.set(false);
        this.historyCleared.emit();
      },
      error: () => this.clearingHistory.set(false),
    });
  }

  exportSkill(name: string) {
    this.exporting.set(true);
    this.skillsService.exportSkill(name).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `${name}.zip`; a.click();
        URL.revokeObjectURL(url);
        this.exporting.set(false);
      },
      error: () => this.exporting.set(false),
    });
  }

  triggerImport() {
    this.importInputRef.nativeElement.click();
  }

  onImportFileSelected(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.importing.set(true);
    this.skillsService.importSkills(file).subscribe({
      next: (res) => {
        this.importing.set(false);
        (event.target as HTMLInputElement).value = '';
        const msg = res.imported.length
          ? `Imported: ${res.imported.join(', ')}` + (res.skipped.length ? ` — skipped (already exist): ${res.skipped.join(', ')}` : '')
          : `All skills already exist — use force to overwrite`;
        this.toast.success(msg);
        this.loadSkills();
      },
      error: (err) => {
        this.importing.set(false);
        (event.target as HTMLInputElement).value = '';
        this.toast.error(err?.error?.detail ?? 'Import failed');
      },
    });
  }

  // ── Form preview ────────────────────────────────────────────────────────────

  openFormPreview(filename: string): void {
    const sk = this.selectedSkill();
    if (!sk) return;
    const fileWithExt = filename.endsWith('.json') ? filename : `${filename}.json`;
    this.skillsService.readFile(sk.name, fileWithExt).subscribe({
      next: (content) => {
        try {
          const schema = JSON.parse(content);
          this.formPreviewTask.emit({
            id: '__preview__',
            taskType: 'form_input',
            status: 'pending',
            title: filename,
            description: '',
            context: { _form_schema: schema },
            assignedTo: '',
            assignedBy: '',
            createdAt: new Date().toISOString(),
          });
        } catch {
          this.toast.error('Invalid JSON in form file');
        }
      },
      error: () => this.toast.error('Could not load form file'),
    });
  }

  /** Load skill detail without emitting skillSelected — used for tab-driven selection to avoid circular events. */
  selectByName(name: string): void {
    if (!name || this.selectedSkill()?.name === name) return;
    this.loading.set(true);
    this.validation.set(null);
    this.skillsService.get(name).subscribe(sk => {
      this.selectedSkill.set(sk);
      this.helperFiles.set(sk.helper_files);
      this.loading.set(false);
    });
  }

  deselect(): void {
    this.selectedSkill.set(null);
    this.helperFiles.set([]);
  }

  downloadFile = (name: string) => {
    const sk = this.selectedSkill()!;
    return this.skillsService.downloadFile(sk.name, name);
  };

  previewFile = (name: string) => {
    const sk = this.selectedSkill()!;
    return this.skillsService.previewFileAsPdf(sk.name, name);
  };

  uploadFile = (file: File) => {
    const sk = this.selectedSkill()!;
    return this.skillsService.uploadFile(sk.name, file);
  };

  deleteFile = (name: string) => {
    const sk = this.selectedSkill()!;
    return this.skillsService.deleteFile(sk.name, name);
  };

  readFile = (name: string) => {
    const sk = this.selectedSkill()!;
    return this.skillsService.readFile(sk.name, name);
  };

  saveHelperFile = (name: string, content: string) => {
    const sk = this.selectedSkill()!;
    return this.skillsService.saveTextFile(sk.name, name, content);
  };

  startDrag(e: PointerEvent) {
    this._dragStartY = e.clientY;
    this._dragStartH = this.detailHeightPx();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }

  onDragMove(e: PointerEvent) {
    if (!(e.currentTarget as HTMLElement).hasPointerCapture(e.pointerId)) return;
    const delta = this._dragStartY - e.clientY; // drag up → taller detail pane
    this.detailHeightPx.set(Math.max(80, Math.min(this._dragStartH + delta, 700)));
  }

  endDrag(e: PointerEvent) {
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
  }
}
