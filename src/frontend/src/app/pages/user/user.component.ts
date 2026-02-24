import { Component, ViewChild, inject, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { SessionsService } from '../../core/services/sessions.service';
import { FileInfo } from '../../core/models/session.models';
import { ChatComponent } from '../../shared/components/chat/chat.component';
import { FileListComponent } from '../../shared/components/file-list/file-list.component';
import { SettingsPanelComponent } from '../../shared/components/settings-panel/settings-panel.component';
import { AuthService } from '../../core/services/auth.service';
import { SettingsService } from '../../core/services/settings.service';
import { ThemeService } from '../../core/services/theme.service';
import { BreakpointService } from '../../core/services/breakpoint.service';

function uuid() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Snap options for desktop and mobile. */
const DESKTOP_SNAPS = [
  { value: '18rem', label: 'Default' },
  { value: '50vw',  label: 'Wide' },
] as const;

const MOBILE_SNAPS = [
  { value: '50vw',  label: '50%' },
  { value: '100vw', label: '100%' },
] as const;

@Component({
  selector: 'app-user',
  standalone: true,
  imports: [CommonModule, ChatComponent, FileListComponent, SettingsPanelComponent],
  templateUrl: './user.component.html',
})
export class UserComponent {
  @ViewChild(ChatComponent) chatComp!: ChatComponent;

  readonly DESKTOP_SNAPS = DESKTOP_SNAPS;
  readonly MOBILE_SNAPS  = MOBILE_SNAPS;
  readonly LEFT_DEFAULT  = '18rem';

  sessionId    = signal(uuid());
  inputFiles   = signal<FileInfo[]>([]);
  outputFiles  = signal<FileInfo[]>([]);
  settingsOpen = signal(false);

  /** CSS width of the left panel. '0px' = closed. */
  leftPanelWidth = signal<string>('18rem');

  readonly theme = inject(ThemeService);
  readonly bp    = inject(BreakpointService);

  constructor(
    private auth: AuthService,
    private sessionsService: SessionsService,
    private router: Router,
    readonly settings: SettingsService,
  ) {
    // Start closed on mobile
    if (this.bp.isMobile()) this.leftPanelWidth.set('0px');

    this.settings.loadSettings().subscribe();

    // On breakpoint change: close on mobile, restore on desktop.
    // Only read bp.isMobile() — reading leftPanelWidth() here would cause the
    // effect to re-run every time the user manually toggles the panel.
    effect(() => {
      if (this.bp.isMobile()) {
        this.leftPanelWidth.set('0px');
      } else {
        this.leftPanelWidth.set(this.LEFT_DEFAULT);
      }
    });
  }

  get userId(): string { return this.auth.currentUser()?.username ?? ''; }

  toggleLeftPanel() {
    this.leftPanelWidth.update(w =>
      w === '0px'
        ? (this.bp.isMobile() ? '50vw' : this.LEFT_DEFAULT)
        : '0px'
    );
  }

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
