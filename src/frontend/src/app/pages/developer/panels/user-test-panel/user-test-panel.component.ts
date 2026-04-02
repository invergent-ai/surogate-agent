import { Component, Output, EventEmitter, ViewChild, ElementRef, HostListener, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { SessionsService } from '../../../../core/services/sessions.service';
import { SettingsService } from '../../../../core/services/settings.service';
import { FileInfo } from '../../../../core/models/session.models';
import { UserResponse } from '../../../../core/models/auth.models';
import { ChatRequest } from '../../../../core/models/chat.models';
import { ChatComponent } from '../../../../shared/components/chat/chat.component';
import { FileListComponent } from '../../../../shared/components/file-list/file-list.component';

function uuid() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

@Component({
  selector: 'app-user-test-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, ChatComponent, FileListComponent],
  templateUrl: './user-test-panel.component.html',
  host: {
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

  // ── User selector ────────────────────────────────────────────────────────
  /** Registered users loaded for the selector. */
  users = signal<UserResponse[]>([]);
  /** Currently selected user, or null for "Dev (my settings)". */
  selectedUser = signal<UserResponse | null>(null);
  /** Text shown in the search input while the dropdown is open. */
  inputValue   = signal('');
  /** Whether the user-selector dropdown is open. */
  dropdownOpen = signal(false);

  /** Users filtered by the current search query. */
  filteredUsers = computed(() => {
    const q = this.inputValue().trim().toLowerCase();
    return q ? this.users().filter(u => u.username.toLowerCase().includes(q)) : this.users();
  });

  /** Info about the model that will be used for the next message. */
  activeModelInfo = computed<{ label: string; thinking: boolean; fallback: boolean; fallbackLabel: string }>(() => {
    const user = this.selectedUser();
    const devModel = this.settingsService.model();
    const devThinking = this.settingsService.thinkingEnabled();

    const shortName = (m: string) => { const p = m.split('/'); return p[p.length - 1]; };

    if (!user) {
      // Dev mode — show dev model directly
      return { label: shortName(devModel), thinking: devThinking, fallback: false, fallbackLabel: '' };
    }
    if (!user.model) {
      // User has no model configured — falls back to dev model
      return { label: '', thinking: devThinking, fallback: true, fallbackLabel: shortName(devModel) };
    }
    return { label: shortName(user.model), thinking: user.thinking_enabled, fallback: false, fallbackLabel: '' };
  });

  /** Chat config overrides derived from the selected user.
   *  Empty when "Dev" is selected so the chat uses the developer's own settings. */
  chatOverrides = computed<Partial<ChatRequest>>(() => {
    const user = this.selectedUser();
    if (!user) return {};
    return {
      model:               user.model               || undefined,
      api_key:             user.api_key             || undefined,
      openrouter_provider: user.openrouter_provider || undefined,
      vllm_url:            user.vllm_url            || undefined,
      vllm_tool_calling:   user.vllm_tool_calling,
      vllm_temperature:    user.vllm_temperature,
      vllm_top_k:          user.vllm_top_k,
      vllm_top_p:          user.vllm_top_p,
      vllm_min_p:          user.vllm_min_p,
      vllm_presence_penalty: user.vllm_presence_penalty,
      vllm_context_length: user.vllm_context_length,
      thinking_enabled:    user.thinking_enabled,
      thinking_budget:     user.thinking_budget,
    };
  });

  @HostListener('document:click', ['$event'])
  onDocumentClick(e: MouseEvent): void {
    if (!this.elRef.nativeElement.contains(e.target)) {
      // Restore display value and close dropdown when clicking outside
      this.inputValue.set(this.selectedUser()?.username ?? '');
      this.dropdownOpen.set(false);
    }
  }

  onSearchFocus(): void {
    this.inputValue.set('');
    this.dropdownOpen.set(true);
  }

  onSearchInput(val: string): void {
    this.inputValue.set(val);
    this.dropdownOpen.set(true);
  }

  selectUser(user: UserResponse | null): void {
    const prev = this.selectedUser();
    const changed = prev?.id !== user?.id;
    this.selectedUser.set(user);
    this.inputValue.set(user?.username ?? '');
    this.dropdownOpen.set(false);
    // Start a fresh session so the selected user's model is active from message 1
    if (changed) this.newSession();
  }

  // ── Panel expansion ───────────────────────────────────────────────────────
  toggleExpanded() {
    const next = !this.expanded();
    this.expanded.set(next);
    if (next && this.users().length === 0) {
      this.settingsService.getUsers().subscribe(u => this.users.set(u));
    }
    next ? this.panelExpanded.emit() : this.panelCollapsed.emit();
  }

  // ── Session / files ───────────────────────────────────────────────────────
  sessionId   = signal(uuid());
  inputFiles  = signal<FileInfo[]>([]);
  outputFiles = signal<FileInfo[]>([]);

  /** Names of files the user uploaded — used to exclude them from the output list. */
  private inputFileNames = new Set<string>();

  private elRef           = inject(ElementRef);
  private settingsService = inject(SettingsService);

  constructor(private sessionsService: SessionsService) {}

  newSession() {
    const oldId = this.sessionId();
    const newId = uuid();

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
    this.sessionsService.listFiles(this.sessionId()).subscribe({
      next: all => this.outputFiles.set(all.filter(f => !this.inputFileNames.has(f.name))),
      error: () => {},
    });
  }

  onInputFilesUploaded(names: string[]) {
    names.forEach(n => this.inputFileNames.add(n));
  }

  onSessionCreated(id: string) {
    this.sessionId.set(id);
    this.inputFiles.set([]);
    this.inputFileNames.clear();
  }

  refreshInputFiles() {
    this.sessionsService.listFiles(this.sessionId()).subscribe(f => {
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
    this.inputFileNames.add(file.name);
    return obs;
  };
}
