import { Component, Output, EventEmitter, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
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
})
export class UserTestPanelComponent {
  @Output() settingsRequired = new EventEmitter<void>();
  @Output() fileOpened       = new EventEmitter<void>();

  expanded = signal(false);
  sessionId = signal(uuid());
  inputFiles  = signal<FileInfo[]>([]);
  outputFiles = signal<FileInfo[]>([]);

  /** Names of files the user uploaded — used to exclude them from the output list. */
  private inputFileNames = new Set<string>();

  constructor(private sessionsService: SessionsService) {}

  newSession() {
    this.sessionId.set(uuid());
    this.inputFiles.set([]);
    this.outputFiles.set([]);
    this.inputFileNames.clear();
  }

  onFilesChanged(_files: string[]) {
    // After agent interaction, refresh all files and show only agent-produced
    // files in the output section (exclude anything the user uploaded as input).
    this.sessionsService.listFiles(this.sessionId()).subscribe(all => {
      this.outputFiles.set(all.filter(f => !this.inputFileNames.has(f.name)));
    });
  }

  onSessionCreated(id: string) {
    this.sessionId.set(id);
    this.refreshInputFiles();
  }

  refreshInputFiles() {
    this.sessionsService.listFiles(this.sessionId()).subscribe(f => {
      this.inputFiles.set(f);
      this.inputFileNames = new Set(f.map(file => file.name));
    });
  }

  refreshOutputFiles() {
    this.sessionsService.listFiles(this.sessionId()).subscribe(all => {
      this.outputFiles.set(all.filter(f => !this.inputFileNames.has(f.name)));
    });
  }

  downloadFile = (name: string)                  => this.sessionsService.downloadFile(this.sessionId(), name);
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
