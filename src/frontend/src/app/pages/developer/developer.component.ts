import { Component, ViewChild, inject, signal, effect, untracked } from '@angular/core';
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
import { SettingsService } from '../../core/services/settings.service';
import { ThemeService } from '../../core/services/theme.service';
import { BreakpointService } from '../../core/services/breakpoint.service';
import { FullscreenService } from '../../core/services/fullscreen.service';

/** Snap options shown in the panel header. */
const DESKTOP_SNAPS = [
  { value: '18rem', label: 'Default' },
  { value: '50vw',  label: 'Wide' },
] as const;

const DESKTOP_SNAPS_RIGHT = [
  { value: '20rem', label: 'Default' },
  { value: '50vw',  label: 'Wide' },
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

  readonly DESKTOP_SNAPS       = DESKTOP_SNAPS;
  readonly DESKTOP_SNAPS_RIGHT = DESKTOP_SNAPS_RIGHT;
  readonly MOBILE_SNAPS        = MOBILE_SNAPS;
  readonly LEFT_DEFAULT        = '18rem';
  readonly RIGHT_DEFAULT       = '20rem';

  activeSkill      = signal('');
  settingsOpen     = signal(false);
  chatHasMessages  = signal(false);

  /** CSS width of each panel. '0px' = closed. */
  leftPanelWidth  = signal<string>('18rem');
  rightPanelWidth = signal<string>('20rem');

  readonly theme = inject(ThemeService);
  readonly bp    = inject(BreakpointService);
  private readonly fullscreenSvc = inject(FullscreenService);

  private _savedRightPanelWidth = '';

  constructor(
    private auth: AuthService,
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

  onActiveSkillChange(name: string) {
    // Only clear the chat when the active skill actually changes
    if (this.activeSkill() !== name) {
      this.activeSkill.set(name);
      this.skillsBrowser.detailHeightPx.set(700);
      if (this.devChat) this.devChat.clearMessages();

      // Sync the left-panel highlight (no-op if skill already shown)
      if (name && this.skillsBrowser) this.skillsBrowser.selectByName(name);
      // Expand the left panel so the skill detail is visible
      if (name) this.expandLeftPanel();
      return;
    }

    this.skillsBrowser.deselect();
    this.onSkillDetailClosed();
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
      this.skillTabs.openOrFocus(name);
      if (this.skillsBrowser) this.skillsBrowser.loadSkills();
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
    this.leftPanelWidth.set(this.bp.isMobile() ? '0px' : this.LEFT_DEFAULT);
  }

  onTestPanelCollapsed() {
    this.rightPanelWidth.set(this.bp.isMobile() ? '0px' : this.RIGHT_DEFAULT);
  }

  onNewSkillRequested() {
    this.activeSkill.set('');
    if (this.devChat) this.devChat.clearMessages();
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
