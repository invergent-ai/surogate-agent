import { Component, Input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ThinkingBlock } from '../../../core/models/chat.models';

@Component({
  selector: 'app-thinking-block',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './thinking-block.component.html',
})
export class ThinkingBlockComponent {
  @Input({ required: true }) block!: ThinkingBlock;
  collapsed = signal(true);
  toggle() { this.collapsed.update(v => !v); }
}
