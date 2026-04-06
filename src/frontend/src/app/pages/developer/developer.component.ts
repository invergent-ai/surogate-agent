import { Component, ViewChild, inject, signal, effect, untracked, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { SkillTabsComponent } from '../../shared/components/skill-tabs/skill-tabs.component';
import { ChatComponent } from '../../shared/components/chat/chat.component';
import { SkillsBrowserComponent } from './panels/skills-browser/skills-browser.component';
import { WorkspacePanelComponent } from './panels/workspace-panel/workspace-panel.component';
import { UserTestPanelComponent } from './panels/user-test-panel/user-test-panel.component';
import { SettingsPanelComponent } from '../../shared/components/settings-panel/settings-panel.component';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog/confirm-dialog.component';
import { AuthService } from '../../core/services/auth.service';
import { SessionsService } from '../../core/services/sessions.service';
import { SettingsService } from '../../core/services/settings.service';
import { ChatMessage } from '../../core/models/chat.models';
import { HumanTask } from '../../core/models/task.models';
import { ThemeService } from '../../core/services/theme.service';
import { BreakpointService } from '../../core/services/breakpoint.service';
import { FullscreenService } from '../../core/services/fullscreen.service';

/** Snap options shown in the panel header. */
const DESKTOP_SNAPS = [
  { value: '18rem', label: 'Default' },
  { value: '50vw',  label: 'Wide' },
] as const;

const DESKTOP_SNAPS_RIGHT = [
  { value: '20rem',  label: 'Default' },
  { value: '50vw',   label: 'Wide' },
  { value: '100vw',  label: 'Full' },
] as const;

const MOBILE_SNAPS = [
  { value: '50vw',  label: '50%' },
  { value: '100vw', label: '100%' },
] as const;

@Component({
  selector: 'app-developer',
  standalone: true,
  imports: [
    CommonModule,
    SkillTabsComponent,
    ChatComponent,
    SkillsBrowserComponent,
    WorkspacePanelComponent,
    UserTestPanelComponent,
    SettingsPanelComponent,
    ConfirmDialogComponent,
  ],
  templateUrl: './developer.component.html',
})
export class DeveloperComponent {
  @ViewChild(SkillTabsComponent) skillTabs!: SkillTabsComponent;
  @ViewChild(SkillsBrowserComponent) skillsBrowser!: SkillsBrowserComponent;
  @ViewChild(ChatComponent) devChat!: ChatComponent;
  @ViewChild(WorkspacePanelComponent) workspacePanel!: WorkspacePanelComponent;

  readonly DESKTOP_SNAPS       = DESKTOP_SNAPS;
  readonly DESKTOP_SNAPS_RIGHT = DESKTOP_SNAPS_RIGHT;
  readonly MOBILE_SNAPS        = MOBILE_SNAPS;
  readonly LEFT_DEFAULT        = '18rem';
  readonly RIGHT_DEFAULT       = '20rem';

  activeSkill      = signal('');
  settingsOpen     = signal(false);
  chatHasMessages  = signal(false);
  formPreviewTask  = signal<HumanTask | null>(null);

  /**
   * Name of the last skill detected mid-stream while on a blank "new skill" tab.
   * Used as a fallback in onMessagesSnapshot so the creation conversation is
   * saved under dev:<name> even though activeSkill is '' at stream end.
   */
  private _pendingSkillName = '';

  /** CSS width of each panel. '0px' = closed. */
  leftPanelWidth  = signal<string>('18rem');
  rightPanelWidth = signal<string>('20rem');

  readonly theme = inject(ThemeService);
  readonly bp    = inject(BreakpointService);
  private readonly fullscreenSvc = inject(FullscreenService);

  private _savedRightPanelWidth = '';

  constructor(
    private auth: AuthService,
    private sessionsService: SessionsService,
    private router: Router,
    readonly settings: SettingsService,
  ) {
    // Start closed on mobile
    if (this.bp.isMobile()) {
      this.leftPanelWidth.set('0px');
      this.rightPanelWidth.set('0px');
    }

    this.settings.loadSettings().subscribe();

    // On breakpoint change: close on mobile, restore on desktop.
    // Only read bp.isMobile() — reading panel widths here would cause the
    // effect to re-run every time the user manually toggles a panel.
    effect(() => {
      if (this.bp.isMobile()) {
        this.leftPanelWidth.set('0px');
        this.rightPanelWidth.set('0px');
      } else {
        this.leftPanelWidth.set(this.LEFT_DEFAULT);
        this.rightPanelWidth.set(this.RIGHT_DEFAULT);
      }
    });

    // When a file viewer goes fullscreen, collapse the right panel.
    // Restore to its previous width when fullscreen exits.
    effect(() => {
      if (this.fullscreenSvc.active()) {
        this._savedRightPanelWidth = untracked(() => this.rightPanelWidth());
        this.rightPanelWidth.set('0px');
      } else if (this._savedRightPanelWidth) {
        this.rightPanelWidth.set(this._savedRightPanelWidth);
        this._savedRightPanelWidth = '';
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

  toggleRightPanel() {
    this.rightPanelWidth.update(w =>
      w === '0px'
        ? (this.bp.isMobile() ? '50vw' : this.RIGHT_DEFAULT)
        : '0px'
    );
  }

  @HostListener('document:keydown', ['$event'])
  onEscapeKey(e: KeyboardEvent) {
    if (e.key !== 'Escape') return;
    const mobile = this.bp.isMobile();
    this.leftPanelWidth.set(mobile ? '0px' : this.LEFT_DEFAULT);
    this.rightPanelWidth.set(mobile ? '0px' : this.RIGHT_DEFAULT);
    this.skillsBrowser?.closeOpenFile();
    this.workspacePanel?.closeOpenFile();
  }

  onActiveSkillChange(name: string) {
    // Only reload when the active skill actually changes
    if (this.activeSkill() !== name) {
      this.activeSkill.set(name);
      this.skillsBrowser.detailHeightPx.set(700);

      if (name && this.devChat) {
        // Load persisted chat history for this skill and restore it visually.
        // Guard the callback: discard stale responses if the user switched
        // tabs before the HTTP request finished.
        this.sessionsService.getHistory(`dev:${name}`).subscribe(history => {
          if (this.activeSkill() !== name || !this.devChat) return;
          const msgs = history.messages as ChatMessage[];
          this.devChat.restoreSession(msgs, `dev:${name}`);
        });
      } else if (this.devChat) {
        this.devChat.clearMessages();
      }

      // Sync the left-panel highlight (no-op if skill already shown)
      if (name && this.skillsBrowser) this.skillsBrowser.selectByName(name);
      // Expand the left panel so the skill detail is visible
      if (name) this.expandLeftPanel();
      return;
    }

    this.skillsBrowser.deselect();
    this.onSkillDetailClosed();
  }

  onMessagesSnapshot(messages: unknown[]) {
    // Prefer the active skill; fall back to _pendingSkillName when on a blank
    // tab (skill just created in this turn).
    const skill = this.activeSkill() || this._pendingSkillName;
    this._pendingSkillName = '';
    if (!skill || messages.length === 0) return;
    this.sessionsService.saveHistory(`dev:${skill}`, messages).subscribe();
  }

  onSkillsLoaded(names: string[]) {
    if (this.skillTabs) this.skillTabs.populateTabs(names);
  }

  onSkillDeleted(name: string) {
    if (this.skillTabs) this.skillTabs.closeTabByName(name);
  }

  onSkillDeleteRequested(name: string) {
    if (this.skillsBrowser) this.skillsBrowser.deleteSkill(name);
  }

  onSkillDetected(name: string) {
    if (this.skillTabs) {
      // ensureTab adds the tab silently — does NOT change activeSkill or clear
      // the chat, so an agent writing a skill file mid-stream can't hijack the
      // developer's current skill focus. loadSkills(true) refreshes the list
      // without emitting detailClosed (which would wipe the active chat).
      this.skillTabs.ensureTab(name);
      if (this.skillsBrowser) this.skillsBrowser.loadSkills(true);
    }
    // When creating a skill from a blank tab (activeSkill is ''), remember the
    // detected name so onMessagesSnapshot can save the creation conversation
    // under dev:<name> instead of discarding it.
    if (!this.activeSkill()) {
      this._pendingSkillName = name;
    }
  }

  onSkillSelectedFromBrowser(name: string) {
    if (this.activeSkill() === name) {
      this.skillsBrowser.deselect();
      this.onSkillDetailClosed();
    } else {
      if (this.skillTabs) this.skillTabs.openOrFocus(name);
      this.expandLeftPanel();
    }
  }

  onSkillDetailClosed() {
    if (this.skillTabs) this.skillTabs.inactivate();
    this.activeSkill.set('');
    if (this.devChat) this.devChat.clearMessages();
    this.leftPanelWidth.set(this.bp.isMobile() ? '0px' : this.LEFT_DEFAULT);
  }

  onTestPanelCollapsed() {
    this.rightPanelWidth.set(this.bp.isMobile() ? '0px' : this.RIGHT_DEFAULT);
  }

  onNewSkillRequested() {
    this.activeSkill.set('');
    if (this.devChat) this.devChat.clearMessages();
  }

  onSkillHistoryCleared() {
    if (this.devChat) this.devChat.clearMessages();
  }

  onAgentResponseDone() {
    if (this.workspacePanel) this.workspacePanel.refresh();
  }

  expandLeftPanel() {
    this.leftPanelWidth.set(this.bp.isMobile() ? '100vw' : '50vw');
  }

  expandRightPanel() {
    this.rightPanelWidth.set(this.bp.isMobile() ? '100vw' : '50vw');
  }

  exit() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
