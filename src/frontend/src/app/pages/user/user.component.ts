import {
  Component, ViewChild, inject, signal, computed, OnInit, AfterViewInit
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { tap } from 'rxjs';
import { SessionsService } from '../../core/services/sessions.service';
import { FileInfo, SessionMeta } from '../../core/models/session.models';
import { ChatMessage } from '../../core/models/chat.models';
import { ChatComponent } from '../../shared/components/chat/chat.component';
import { FileListComponent } from '../../shared/components/file-list/file-list.component';
import { SettingsPanelComponent } from '../../shared/components/settings-panel/settings-panel.component';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog/confirm-dialog.component';
import { SessionsListComponent } from './sessions-list/sessions-list.component';
import { AuthService } from '../../core/services/auth.service';
import { ConfirmDialogService } from '../../core/services/confirm-dialog.service';
import { SettingsService } from '../../core/services/settings.service';
import { ThemeService } from '../../core/services/theme.service';
import { BreakpointService } from '../../core/services/breakpoint.service';

// ── Quirky name generator ────────────────────────────────────────────────────
const ADJECTIVES = [
  'Cosmic', 'Funky', 'Witty', 'Turbo', 'Zesty', 'Snazzy', 'Quirky', 'Plucky',
  'Groovy', 'Bouncy', 'Crispy', 'Wobbly', 'Sparkly', 'Fizzy', 'Swoopy', 'Nifty',
  'Jolly', 'Peppy', 'Zippy', 'Wacky', 'Giddy', 'Cheeky', 'Sassy', 'Brainy',
  'Snappy', 'Dandy', 'Swanky', 'Feisty', 'Perky', 'Dapper',
];
const NOUNS = [
  'Penguin', 'Muffin', 'Kazoo', 'Platypus', 'Quasar', 'Noodle', 'Rocket', 'Waffle',
  'Gizmo', 'Nebula', 'Pickle', 'Panda', 'Biscuit', 'Tornado', 'Hamster', 'Pretzel',
  'Unicorn', 'Narwhal', 'Bagel', 'Wizard', 'Goblin', 'Teapot', 'Crumpet', 'Mongoose',
  'Bumblebee', 'Donut', 'Trombone', 'Capybara', 'Spatula', 'Quokka',
];

function generateSessionName(): string {
  const adj  = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)];
  const noun = NOUNS[Math.floor(Math.random() * NOUNS.length)];
  return `${adj} ${noun}`;
}

function uuid(): string {
  return crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// ── Snap constants ───────────────────────────────────────────────────────────
const DESKTOP_SNAPS = [
  { value: '18rem', label: 'Default' },
  { value: '50vw',  label: 'Wide' },
] as const;

const MOBILE_SNAPS = [
  { value: '50vw',  label: '50%' },
  { value: '100vw', label: '100%' },
] as const;

// ── Component ────────────────────────────────────────────────────────────────
@Component({
  selector: 'app-user',
  standalone: true,
  imports: [
    CommonModule,
    ChatComponent,
    FileListComponent,
    SettingsPanelComponent,
    ConfirmDialogComponent,
    SessionsListComponent,
  ],
  templateUrl: './user.component.html',
})
export class UserComponent implements OnInit, AfterViewInit {
  @ViewChild(ChatComponent) chatComp!: ChatComponent;

  readonly DESKTOP_SNAPS = DESKTOP_SNAPS;
  readonly MOBILE_SNAPS  = MOBILE_SNAPS;
  readonly LEFT_DEFAULT  = '18rem';

  sessions    = signal<SessionMeta[]>([]);
  sessionId   = signal<string>('');
  sessionName = computed(() => this.sessions().find(s => s.sessionId === this.sessionId())?.name ?? '');
  inputFiles  = signal<FileInfo[]>([]);
  outputFiles = signal<FileInfo[]>([]);
  settingsOpen = signal(false);

  /** Height (px) of the sessions pane; adjusted by the drag separator. */
  sessionsPanelHeightPx = signal<number>(180);
  private _dragStartY = 0;
  private _dragStartH = 0;

  leftPanelWidth = signal<string>('18rem');

  readonly theme   = inject(ThemeService);
  readonly bp      = inject(BreakpointService);
  private confirmSvc = inject(ConfirmDialogService);

  constructor(
    private auth: AuthService,
    private sessionsService: SessionsService,
    private router: Router,
    readonly settings: SettingsService,
  ) {
    if (this.bp.isMobile()) this.leftPanelWidth.set('0px');
    this.settings.loadSettings().subscribe();
  }

  ngOnInit() {
    // Intentionally empty — session loading happens after the view is ready.
  }

  ngAfterViewInit() {
    this.sessionsService.listMeta().subscribe(sessions => {
      this.sessions.set(sessions);
      if (sessions.length > 0) {
        this._activateSession(sessions[0], true);
      } else {
        this.createNewSession();
      }
    });
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  get userId(): string { return this.auth.currentUser()?.username ?? ''; }

  createNewSession() {
    const meta: SessionMeta = {
      sessionId: uuid(),
      name:      generateSessionName(),
      createdAt: new Date().toISOString(),
    };
    this.sessions.update(s => [meta, ...s]);
    this._activateSession(meta, false);
    // Persist to DB
    this.sessionsService.createMeta(meta.sessionId, meta.name).subscribe();
  }

  /** Called from header "New session" button. */
  newSession() { this.createNewSession(); }

  switchToSession(meta: SessionMeta) {
    this._activateSession(meta, true);
  }

  renameSession(sessionId: string, name: string) {
    this.sessions.update(s => s.map(m => m.sessionId === sessionId ? { ...m, name } : m));
    this.sessionsService.updateMeta(sessionId, name).subscribe();
  }

  async deleteSession(sessionId: string) {
    const session = this.sessions().find(s => s.sessionId === sessionId);
    const name = session?.name ?? sessionId;
    const ok = await this.confirmSvc.confirm(
      `Delete session "${name}"? Its chat history will be permanently removed.`,
      { title: 'Delete session' },
    );
    if (!ok) return;

    const wasActive = sessionId === this.sessionId();
    this.sessions.update(s => s.filter(m => m.sessionId !== sessionId));
    // Delete metadata + chat history from DB; also try workspace cleanup
    this.sessionsService.deleteMeta(sessionId).subscribe();
    this.sessionsService.delete(sessionId).subscribe({ error: () => {} });

    if (wasActive) {
      const remaining = this.sessions();
      if (remaining.length > 0) {
        this._activateSession(remaining[0], true);
      } else {
        this.createNewSession();
      }
    }
  }

  // ── Files ──────────────────────────────────────────────────────────────────

  onSessionCreated(id: string) {
    const old = this.sessionId();
    if (old === id) return;
    // Backend assigned a canonical ID — update the session's record
    this.sessions.update(s => s.map(m => m.sessionId === old ? { ...m, sessionId: id } : m));
    // Update the DB record: create new meta with the canonical id + delete old
    const renamed = this.sessions().find(m => m.sessionId === id);
    if (renamed) {
      this.sessionsService.createMeta(id, renamed.name).subscribe();
      if (old && old !== id) this.sessionsService.deleteMeta(old).subscribe();
    }
    this.sessionId.set(id);
    this._refreshFiles();
  }

  onFilesChanged(_files: string[]) { this._refreshFiles(); }

  refreshInputFiles()  { this._refreshFiles(); }
  refreshOutputFiles() { this._refreshFiles(); }

  expandLeftPanel() {
    this.leftPanelWidth.set(this.bp.isMobile() ? '100vw' : '50vw');
  }

  toggleLeftPanel() {
    this.leftPanelWidth.update(w =>
      w === '0px'
        ? (this.bp.isMobile() ? '50vw' : this.LEFT_DEFAULT)
        : '0px'
    );
  }

  /** Called when the chat component finishes a streaming turn. */
  onMessagesSnapshot(messages: unknown[]) {
    const sid = this.sessionId();
    if (!sid || messages.length === 0) return;
    this.sessionsService.saveHistory(sid, messages).subscribe();
  }

  // ── Draggable separator ────────────────────────────────────────────────────

  startDrag(e: PointerEvent) {
    this._dragStartY = e.clientY;
    this._dragStartH = this.sessionsPanelHeightPx();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }

  onDragMove(e: PointerEvent) {
    if (!(e.currentTarget as HTMLElement).hasPointerCapture(e.pointerId)) return;
    const delta = e.clientY - this._dragStartY;
    this.sessionsPanelHeightPx.set(Math.max(60, Math.min(this._dragStartH + delta, 500)));
  }

  endDrag(e: PointerEvent) {
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
  }

  // ── File operation closures ───────────────────────────────────────────────

  downloadFile    = (name: string)                  => this.sessionsService.downloadFile(this.sessionId(), name);
  uploadFile      = (file: File)                    => this.sessionsService.uploadFile(this.sessionId(), file).pipe(
                      tap(() => this._trackInputFile(file.name)));
  deleteInputFile = (name: string)                  => this.sessionsService.deleteFile(this.sessionId(), name).pipe(
                      tap(() => this._untrackInputFile(name)));
  deleteFile      = (name: string)                  => this.sessionsService.deleteFile(this.sessionId(), name);
  readFile        = (name: string)                  => this.sessionsService.readFile(this.sessionId(), name);
  saveFile        = (name: string, content: string) => this.sessionsService.saveTextFile(this.sessionId(), name, content);

  exit() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }

  // ── Private helpers ────────────────────────────────────────────────────────

  private _activateSession(meta: SessionMeta, restoreMessages: boolean) {
    this.sessionId.set(meta.sessionId);
    this.inputFiles.set([]);
    this.outputFiles.set([]);

    if (restoreMessages && this.chatComp) {
      this.sessionsService.getHistory(meta.sessionId).subscribe(history => {
        if (history.messages.length > 0) {
          this.chatComp.restoreSession(history.messages as ChatMessage[], meta.sessionId);
        } else {
          this.chatComp.restoreSession([], meta.sessionId);
        }
      });
    } else if (this.chatComp) {
      this.chatComp.restoreSession([], meta.sessionId);
    }

    if (meta.sessionId) this._refreshFiles();
  }

  private _refreshFiles() {
    const id = this.sessionId();
    if (!id) return;
    this.sessionsService.listFiles(id).subscribe(files => {
      const inputNames = this._getInputFileNames();
      this.inputFiles.set(files.filter(f => inputNames.has(f.name)));
      this.outputFiles.set(files.filter(f => !inputNames.has(f.name)));
    });
  }

  // ── Input-file tracking (sessionStorage, keyed by session ID) ──────────────

  private _storageKey(): string {
    return `surogate-input-files-${this.sessionId()}`;
  }

  private _getInputFileNames(): Set<string> {
    try {
      const raw = sessionStorage.getItem(this._storageKey());
      return raw ? new Set(JSON.parse(raw) as string[]) : new Set();
    } catch { return new Set(); }
  }

  private _trackInputFile(name: string): void {
    const names = this._getInputFileNames();
    names.add(name);
    sessionStorage.setItem(this._storageKey(), JSON.stringify([...names]));
  }

  private _untrackInputFile(name: string): void {
    const names = this._getInputFileNames();
    names.delete(name);
    sessionStorage.setItem(this._storageKey(), JSON.stringify([...names]));
  }
}
