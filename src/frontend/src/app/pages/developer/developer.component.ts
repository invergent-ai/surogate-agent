import { Component, ViewChild, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { SkillTabsComponent } from '../../shared/components/skill-tabs/skill-tabs.component';
import { ChatComponent } from '../../shared/components/chat/chat.component';
import { SkillsBrowserComponent } from './panels/skills-browser/skills-browser.component';
import { WorkspacePanelComponent } from './panels/workspace-panel/workspace-panel.component';
import { UserTestPanelComponent } from './panels/user-test-panel/user-test-panel.component';
import { SettingsPanelComponent } from '../../shared/components/settings-panel/settings-panel.component';
import { AuthService } from '../../core/services/auth.service';
import { SettingsService } from '../../core/services/settings.service';
import { ThemeService } from '../../core/services/theme.service';

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
  ],
  templateUrl: './developer.component.html',
})
export class DeveloperComponent {
  @ViewChild(SkillTabsComponent) skillTabs!: SkillTabsComponent;
  @ViewChild(SkillsBrowserComponent) skillsBrowser!: SkillsBrowserComponent;
  @ViewChild(ChatComponent) devChat!: ChatComponent;

  activeSkill = signal('');
  settingsOpen = signal(false);

  readonly theme = inject(ThemeService);

  constructor(
    private auth: AuthService,
    private router: Router,
    readonly settings: SettingsService,
  ) {
    // Load user's stored model/api_key from the server on page init
    this.settings.loadSettings().subscribe();
  }

  get userId(): string { return this.auth.currentUser()?.username ?? ''; }

  onActiveSkillChange(name: string) {
    this.activeSkill.set(name);
    if (this.devChat) this.devChat.clearMessages();
  }

  onSkillDetected(name: string) {
    if (this.skillTabs) {
      this.skillTabs.openOrFocus(name);
      if (this.skillsBrowser) this.skillsBrowser.loadSkills();
    }
  }

  onSkillSelectedFromBrowser(name: string) {
    if (this.skillTabs) this.skillTabs.openOrFocus(name);
  }

  onNewSkillRequested() {
    this.activeSkill.set('');
    if (this.devChat) this.devChat.clearMessages();
  }

  exit() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
