import { Component, ViewChild, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { SessionsService } from '../../core/services/sessions.service';
import { FileInfo } from '../../core/models/session.models';
import { ChatComponent } from '../../shared/components/chat/chat.component';
import { FileListComponent } from '../../shared/components/file-list/file-list.component';
import { SettingsPanelComponent } from '../../shared/components/settings-panel/settings-panel.component';
import { AuthService } from '../../core/services/auth.service';
import { SettingsService } from '../../core/services/settings.service';

function uuid() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

@Component({
  selector: 'app-user',
  standalone: true,
  imports: [CommonModule, ChatComponent, FileListComponent, SettingsPanelComponent],
  templateUrl: './user.component.html',
})
export class UserComponent {
  @ViewChild(ChatComponent) chatComp!: ChatComponent;

  sessionId    = signal(uuid());
  inputFiles   = signal<FileInfo[]>([]);
  outputFiles  = signal<FileInfo[]>([]);
  settingsOpen = signal(false);

  constructor(
    private auth: AuthService,
    private sessionsService: SessionsService,
    private router: Router,
    readonly settings: SettingsService,
  ) {}

  get userId(): string { return this.auth.currentUser()?.username ?? ''; }

  newSession() {
    this.sessionId.set(uuid());
    this.inputFiles.set([]);
    this.outputFiles.set([]);
    if (this.chatComp) this.chatComp.clearMessages();
  }

  onSessionCreated(id: string) {
    this.sessionId.set(id);
    this.refreshInputFiles();
  }

  onFilesChanged(files: string[]) {
    this.refreshOutputFiles();
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

  exit() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
