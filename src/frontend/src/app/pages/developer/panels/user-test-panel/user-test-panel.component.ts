import { Component, Input, signal, OnChanges, SimpleChanges } from '@angular/core';
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
  expanded = signal(false);
  sessionId = signal(uuid());
  inputFiles  = signal<FileInfo[]>([]);
  outputFiles = signal<FileInfo[]>([]);

  constructor(private sessionsService: SessionsService) {}

  newSession() {
    this.sessionId.set(uuid());
    this.inputFiles.set([]);
    this.outputFiles.set([]);
  }

  onFilesChanged(files: string[]) {
    this.refreshOutputFiles();
  }

  onSessionCreated(id: string) {
    this.sessionId.set(id);
    this.refreshInputFiles();
  }

  refreshInputFiles() {
    this.sessionsService.listFiles(this.sessionId()).subscribe(f => this.inputFiles.set(f));
  }

  refreshOutputFiles() {
    this.sessionsService.listFiles(this.sessionId()).subscribe(f => this.outputFiles.set(f));
  }

  downloadFile = (name: string) => this.sessionsService.downloadFile(this.sessionId(), name);
  uploadFile   = (file: File)   => this.sessionsService.uploadFile(this.sessionId(), file);
  deleteFile   = (name: string) => this.sessionsService.deleteFile(this.sessionId(), name);
}
