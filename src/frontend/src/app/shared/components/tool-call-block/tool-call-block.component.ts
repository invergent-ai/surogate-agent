import { Component, Input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToolBlock } from '../../../core/models/chat.models';

@Component({
  selector: 'app-tool-call-block',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './tool-call-block.component.html',
})
export class ToolCallBlockComponent {
  @Input({ required: true }) block!: ToolBlock;
  collapsed = signal(true);
  toggle() { this.collapsed.update(v => !v); }

  get argsJson(): string {
    try { return JSON.stringify(this.block.args, null, 2); }
    catch { return String(this.block.args); }
  }
}
