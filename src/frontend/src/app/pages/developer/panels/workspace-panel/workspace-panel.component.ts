import { Component, Input, Output, EventEmitter, signal, OnChanges, SimpleChanges } from '@angular/core';
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
export class WorkspacePanelComponent implements OnChanges {
  @Input() skill = '';
  @Output() fileOpened = new EventEmitter<void>();

  files = signal<FileInfo[]>([]);
  loading = signal(false);
  expanded = signal(true);

  constructor(private workspaceService: WorkspaceService) {}

  ngOnChanges(changes: SimpleChanges) {
    if (changes['skill'] && this.skill) this.loadFiles();
  }

  loadFiles() {
    if (!this.skill) { this.files.set([]); return; }
    this.loading.set(true);
    this.workspaceService.listFiles(this.skill).subscribe({
      next: files => { this.files.set(files); this.loading.set(false); },
      error: () => { this.files.set([]); this.loading.set(false); },
    });
  }

  cleanWorkspace() {
    if (!this.skill || !confirm(`Delete all workspace files for '${this.skill}'?`)) return;
    this.workspaceService.delete(this.skill).subscribe(() => this.loadFiles());
  }

  download  = (name: string)                  => this.workspaceService.downloadFile(this.skill, name);
  upload    = (file: File)                    => this.workspaceService.uploadFile(this.skill, file);
  delete    = (name: string)                  => this.workspaceService.deleteFile(this.skill, name);
  readFile  = (name: string)                  => this.workspaceService.readFile(this.skill, name);
  saveFile  = (name: string, content: string) => this.workspaceService.saveTextFile(this.skill, name, content);
}
