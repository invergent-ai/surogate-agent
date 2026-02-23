import { Component, ViewChild, signal } from '@angular/core';
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

  constructor(
    private auth: AuthService,
    private router: Router,
    readonly settings: SettingsService,
  ) {}

  get userId(): string { return this.auth.currentUser()?.username ?? ''; }

  onActiveSkillChange(name: string) {
    this.activeSkill.set(name);
    // Reset dev chat when switching skills
    if (this.devChat) this.devChat.clearMessages();
  }

  onSkillDetected(name: string) {
    // Auto-open tab when agent writes to a skill path
    if (this.skillTabs) {
      this.skillTabs.openOrFocus(name);
      // Refresh skills browser too
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
