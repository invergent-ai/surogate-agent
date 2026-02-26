import { Component, Input, Output, EventEmitter, signal, computed, OnInit, OnChanges, SimpleChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ConfirmDialogService } from '../../../../core/services/confirm-dialog.service';
import { WorkspaceService } from '../../../../core/services/workspace.service';
import { FileInfo } from '../../../../core/models/session.models';
import { FileListComponent } from '../../../../shared/components/file-list/file-list.component';

@Component({
  selector: 'app-workspace-panel',
  standalone: true,
  imports: [CommonModule, FileListComponent],
  templateUrl: './workspace-panel.component.html',
})
export class WorkspacePanelComponent implements OnInit, OnChanges {
  @Input() skill = '';
  @Output() fileOpened = new EventEmitter<void>();

  files           = signal<FileInfo[]>([]);
  loading         = signal(false);
  expanded        = signal(true);
  localFolder     = signal('');
  existingFolders = signal<string[]>([]);

  /** The folder actually used for API calls: pinned skill takes precedence over typed folder. */
  effectiveFolder = computed(() => this.skill || this.localFolder());

  private confirmSvc = inject(ConfirmDialogService);
  private _folderDebounce?: ReturnType<typeof setTimeout>;

  constructor(private workspaceService: WorkspaceService) {}

  ngOnInit() {
    // Populate autocomplete suggestions from existing workspace folders.
    this.workspaceService.list().subscribe({
      next: ws => this.existingFolders.set(ws.map(w => w.skill)),
      error: () => {},
    });
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['skill']) {
      if (this.skill) {
        this.localFolder.set('');
        this.loadFiles();
      } else {
        this.files.set([]);
      }
    }
  }

  onFolderInput(value: string) {
    const trimmed = value.trim();
    this.localFolder.set(trimmed);
    clearTimeout(this._folderDebounce);
    if (trimmed && this.existingFolders().includes(trimmed)) {
      this._folderDebounce = setTimeout(() => this.loadFiles(), 400);
    } else {
      this.files.set([]);
    }
  }

  loadFiles() {
    const folder = this.effectiveFolder();
    if (!folder) { this.files.set([]); return; }
    this.loading.set(true);
    // Use get() instead of listFiles() so we first confirm the workspace exists
    // (404 → empty state) rather than hitting /{skill}/files on a non-existent path.
    this.workspaceService.get(folder).subscribe({
      next: ws => {
        this.files.set(ws.files);
        this.loading.set(false);
        // Keep autocomplete list fresh after a successful load
        if (!this.existingFolders().includes(folder)) {
          this.existingFolders.update(f => [...f, folder]);
        }
      },
      error: () => { this.files.set([]); this.loading.set(false); },
    });
  }

  async cleanWorkspace() {
    const folder = this.effectiveFolder();
    if (!folder) return;
    const ok = await this.confirmSvc.confirm(
      `Delete all workspace files for "${folder}"? This cannot be undone.`,
      { title: 'Clean workspace', actionLabel: 'Clean' },
    );
    if (!ok) return;
    this.workspaceService.delete(folder).subscribe(() => this.loadFiles());
  }

  download  = (name: string)                  => this.workspaceService.downloadFile(this.effectiveFolder(), name);
  upload    = (file: File)                    => this.workspaceService.uploadFile(this.effectiveFolder(), file);
  delete    = (name: string)                  => this.workspaceService.deleteFile(this.effectiveFolder(), name);
  readFile  = (name: string)                  => this.workspaceService.readFile(this.effectiveFolder(), name);
  saveFile  = (name: string, content: string) => this.workspaceService.saveTextFile(this.effectiveFolder(), name, content);
}
