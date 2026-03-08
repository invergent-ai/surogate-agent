import { Component, Output, EventEmitter, ViewChild, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { SessionsService } from '../../../../core/services/sessions.service';
import { FileInfo } from '../../../../core/models/session.models';
import { ChatComponent } from '../../../../shared/components/chat/chat.component';
import { FileListComponent } from '../../../../shared/components/file-list/file-list.component';

function uuid() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

@Component({
  selector: 'app-user-test-panel',
  standalone: true,
  imports: [CommonModule, ChatComponent, FileListComponent],
  templateUrl: './user-test-panel.component.html',
  host: {
    // When expanded the host element must participate in the parent flex-col as
    // a flex-1 child, and must itself be a flex-col so that the inner div's
    // own flex-1 child resolves against a bounded height.
    '[class.flex-1]':   'expanded()',
    '[class.min-h-0]':  'expanded()',
    '[class.flex]':     'expanded()',
    '[class.flex-col]': 'expanded()',
  },
})
export class UserTestPanelComponent {
  @ViewChild(ChatComponent) chatComp?: ChatComponent;

  @Output() settingsRequired = new EventEmitter<void>();
  @Output() fileOpened       = new EventEmitter<void>();
  @Output() panelExpanded    = new EventEmitter<void>();
  @Output() panelCollapsed   = new EventEmitter<void>();

  expanded = signal(false);

  toggleExpanded() {
    const next = !this.expanded();
    this.expanded.set(next);
    next ? this.panelExpanded.emit() : this.panelCollapsed.emit();
  }
  sessionId = signal(uuid());
  inputFiles  = signal<FileInfo[]>([]);
  outputFiles = signal<FileInfo[]>([]);

  /** Names of files the user uploaded — used to exclude them from the output list. */
  private inputFileNames = new Set<string>();

  constructor(private sessionsService: SessionsService) {}

  newSession() {
    const oldId = this.sessionId();
    const newId = uuid();

    // Delete all traces of the old session in parallel; ignore 404s.
    forkJoin([
      this.sessionsService.delete(oldId).pipe(catchError(() => of(null))),
      this.sessionsService.clearHistory(oldId).pipe(catchError(() => of(null))),
      this.sessionsService.deleteMeta(oldId).pipe(catchError(() => of(null))),
    ]).subscribe(() => {
      this.sessionId.set(newId);
      this.inputFiles.set([]);
      this.outputFiles.set([]);
      this.inputFileNames.clear();
      this.chatComp?.restoreSession([], newId);
    });
  }

  onFilesChanged(_files: string[]) {
    // After agent interaction, refresh all files and show only agent-produced
    // files in the output section (exclude anything the user uploaded as input).
    this.sessionsService.listFiles(this.sessionId()).subscribe({
      next: all => this.outputFiles.set(all.filter(f => !this.inputFileNames.has(f.name))),
      error: () => {},   // session dir may not exist yet (empty session)
    });
  }

  onSessionCreated(id: string) {
    this.sessionId.set(id);
    this.inputFiles.set([]);
    this.inputFileNames.clear();
  }

  refreshInputFiles() {
    this.sessionsService.listFiles(this.sessionId()).subscribe(f => {
      // Only show files the user explicitly uploaded — never reclassify output files as inputs.
      this.inputFiles.set(f.filter(file => this.inputFileNames.has(file.name)));
    });
  }

  refreshOutputFiles() {
    this.sessionsService.listFiles(this.sessionId()).subscribe(all => {
      this.outputFiles.set(all.filter(f => !this.inputFileNames.has(f.name)));
    });
  }

  downloadFile = (name: string)                  => this.sessionsService.downloadFile(this.sessionId(), name);
  previewFile  = (name: string)                  => this.sessionsService.previewFile(this.sessionId(), name);
  deleteFile   = (name: string)                  => this.sessionsService.deleteFile(this.sessionId(), name);
  readFile     = (name: string)                  => this.sessionsService.readFile(this.sessionId(), name);
  saveFile     = (name: string, content: string) => this.sessionsService.saveTextFile(this.sessionId(), name, content);

  uploadFile = (file: File) => {
    const obs = this.sessionsService.uploadFile(this.sessionId(), file);
    // Track the uploaded filename so it is excluded from the output list later.
    this.inputFileNames.add(file.name);
    return obs;
  };
}
