import { Component, Input, Output, EventEmitter, signal, computed, OnInit, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
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
    this.localFolder.set(value.trim());
    if (value.trim()) this.loadFiles();
    else this.files.set([]);
  }

  loadFiles() {
    const folder = this.effectiveFolder();
    if (!folder) { this.files.set([]); return; }
    this.loading.set(true);
    this.workspaceService.listFiles(folder).subscribe({
      next: files => { this.files.set(files); this.loading.set(false); },
      error: () => { this.files.set([]); this.loading.set(false); },
    });
  }

  cleanWorkspace() {
    const folder = this.effectiveFolder();
    if (!folder || !confirm(`Delete all workspace files for '${folder}'?`)) return;
    this.workspaceService.delete(folder).subscribe(() => this.loadFiles());
  }

  download  = (name: string)                  => this.workspaceService.downloadFile(this.effectiveFolder(), name);
  upload    = (file: File)                    => this.workspaceService.uploadFile(this.effectiveFolder(), file);
  delete    = (name: string)                  => this.workspaceService.deleteFile(this.effectiveFolder(), name);
  readFile  = (name: string)                  => this.workspaceService.readFile(this.effectiveFolder(), name);
  saveFile  = (name: string, content: string) => this.workspaceService.saveTextFile(this.effectiveFolder(), name, content);
}
