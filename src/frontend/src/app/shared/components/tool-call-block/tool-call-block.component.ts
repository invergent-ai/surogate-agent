import { Component, Input, signal, DoCheck } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToolBlock, SubagentActivityItem } from '../../../core/models/chat.models';

@Component({
  selector: 'app-tool-call-block',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './tool-call-block.component.html',
})
export class ToolCallBlockComponent implements DoCheck {
  @Input({ required: true }) block!: ToolBlock;
  collapsed = signal(true);
  saCollapsed = signal(true);
  itemCollapsed = signal<Record<number, boolean>>({});

  private _initialized = false;
  private _prevResult: string | undefined = undefined;
  private _prevHasSa = false;

  ngDoCheck() {
    if (!this.block || this.block.name !== 'task') return;

    const hasResult = this.block.result !== undefined;
    const hasSa = !!this.block.subagentActivity;

    if (!this._initialized) {
      this._initialized = true;
      // Auto-expand while task is running
      if (!hasResult) this.collapsed.set(false);
      this._prevResult = this.block.result;
      this._prevHasSa = hasSa;
      return;
    }

    // Task just finished: auto-collapse main block
    if (hasResult && this._prevResult === undefined) {
      this.collapsed.set(true);
    }

    // Subagent activity just arrived: re-expand main block + expand SA section
    if (hasSa && !this._prevHasSa) {
      this.collapsed.set(false);
      this.saCollapsed.set(false);
    }

    this._prevResult = this.block.result;
    this._prevHasSa = hasSa;
  }

  toggle() { this.collapsed.update(v => !v); }
  toggleSa() { this.saCollapsed.update(v => !v); }

  toggleItem(idx: number) {
    this.itemCollapsed.update(m => ({ ...m, [idx]: !m[idx] }));
  }

  isItemCollapsed(idx: number): boolean {
    return this.itemCollapsed()[idx] !== false; // default collapsed
  }

  get argsJson(): string {
    try { return JSON.stringify(this.block.args, null, 2); }
    catch { return String(this.block.args); }
  }

  itemArgsJson(item: SubagentActivityItem): string {
    try { return JSON.stringify(item.args, null, 2); }
    catch { return String(item.args); }
  }
}
