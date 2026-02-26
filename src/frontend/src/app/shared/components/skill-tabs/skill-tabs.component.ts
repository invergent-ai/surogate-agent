import {
  Component, Input, Output, EventEmitter, signal, computed, OnChanges
} from '@angular/core';
import { CommonModule } from '@angular/common';

export interface SkillTab {
  name: string;   // empty string = "new skill"
  dirty: boolean;
}

const PAGE_SIZE = 5;

@Component({
  selector: 'app-skill-tabs',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './skill-tabs.component.html',
})
export class SkillTabsComponent {
  @Output() activeSkillChange    = new EventEmitter<string>();
  @Output() newSkillRequested    = new EventEmitter<void>();
  @Output() skillDeleteRequested = new EventEmitter<string>();

  tabs = signal<SkillTab[]>([]);
  activeIndex = signal(-1);
  pageStart = signal(0);

  visibleTabs = computed(() => {
    const start = this.pageStart();
    return this.tabs().slice(start, start + PAGE_SIZE);
  });

  canScrollLeft = computed(() => this.pageStart() > 0);
  canScrollRight = computed(() => this.pageStart() + PAGE_SIZE < this.tabs().length);

  activeSkill = computed(() => {
    const idx = this.activeIndex();
    const tab = this.tabs()[idx];
    return tab?.name ?? '';
  });

  /** Called on initial page load: populate all skill tabs with no selection. */
  populateTabs(names: string[]): void {
    if (this.tabs().length > 0) return; // already populated; don't reset
    this.tabs.set(names.map(name => ({ name, dirty: false })));
    this.activeIndex.set(-1);
  }

  openOrFocus(name: string): void {
    const existing = this.tabs().findIndex(t => t.name === name);
    if (existing >= 0) {
      this.setActive(existing);
    } else {
      const newTabs = [...this.tabs(), { name, dirty: false }];
      this.tabs.set(newTabs);
      this.setActive(newTabs.length - 1);
    }
    // setActive already emitted; no second emit needed
  }

  setActive(index: number): void {
    const tab = this.tabs()[index];
    if (this.activeIndex() === index) {
      this.inactivate();
      if (tab) this.activeSkillChange.emit(tab.name);
      return;
    }

    this.activeIndex.set(index);
    // Keep active tab visible
    if (index < this.pageStart()) {
      this.pageStart.set(index);
    } else if (index >= this.pageStart() + PAGE_SIZE) {
      this.pageStart.set(index - PAGE_SIZE + 1);
    }
    if (tab) this.activeSkillChange.emit(tab.name);
  }

  inactivate(): void {
    this.activeIndex.set(-1);
  }

  closeTab(index: number, event: MouseEvent): void {
    event.stopPropagation();
    const tab = this.tabs()[index];
    if (tab?.name) {
      // Named tabs: delegate deletion (with confirmation) to the parent
      this.skillDeleteRequested.emit(tab.name);
    } else {
      // Unnamed "new skill" tab: just close locally
      const tabs = [...this.tabs()];
      tabs.splice(index, 1);
      this.tabs.set(tabs);
      const newActive = Math.min(this.activeIndex(), tabs.length - 1);
      this.activeIndex.set(newActive);
      this.pageStart.set(Math.max(0, Math.min(this.pageStart(), tabs.length - PAGE_SIZE)));
      if (newActive >= 0) this.activeSkillChange.emit(tabs[newActive]?.name ?? '');
    }
  }

  /** Close the tab for a specific skill name (called externally when skill is deleted). */
  closeTabByName(name: string): void {
    const idx = this.tabs().findIndex(t => t.name === name);
    if (idx < 0) return;
    const wasActive = idx === this.activeIndex();
    const tabs = [...this.tabs()];
    tabs.splice(idx, 1);
    this.tabs.set(tabs);

    let newActive = this.activeIndex();
    if (newActive === idx) {
      newActive = Math.min(idx, tabs.length - 1);
      this.activeIndex.set(newActive);
    } else if (newActive > idx) {
      this.activeIndex.set(newActive - 1);
    }
    this.pageStart.set(Math.max(0, Math.min(this.pageStart(), Math.max(0, tabs.length - PAGE_SIZE))));

    // Only emit if the active tab changed — avoids unnecessary chat clears
    if (wasActive) {
      const newName = newActive >= 0 ? (tabs[newActive]?.name ?? '') : '';
      this.activeSkillChange.emit(newName);
    }
  }

  scrollLeft(): void {
    this.pageStart.update(v => Math.max(0, v - 1));
  }

  scrollRight(): void {
    this.pageStart.update(v => Math.min(v + 1, this.tabs().length - PAGE_SIZE));
  }

  newSkill(): void {
    // Add a blank "new skill" tab
    const newTabs = [...this.tabs(), { name: '', dirty: false }];
    this.tabs.set(newTabs);
    this.setActive(newTabs.length - 1);
    this.newSkillRequested.emit();
  }

  tabLabel(tab: SkillTab): string {
    return tab.name || '✦ new skill';
  }

  isActive(index: number): boolean {
    return this.activeIndex() === this.pageStart() + index;
  }

  globalIndex(localIndex: number): number {
    return this.pageStart() + localIndex;
  }
}
