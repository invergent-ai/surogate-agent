import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatMessage, MessageBlock } from '../../../core/models/chat.models';
import { ThinkingBlockComponent } from '../thinking-block/thinking-block.component';
import { ToolCallBlockComponent } from '../tool-call-block/tool-call-block.component';

@Component({
  selector: 'app-message-bubble',
  standalone: true,
  imports: [CommonModule, ThinkingBlockComponent, ToolCallBlockComponent],
  templateUrl: './message-bubble.component.html',
})
export class MessageBubbleComponent {
  @Input({ required: true }) message!: ChatMessage;

  isThinking(block: MessageBlock): block is import('../../../core/models/chat.models').ThinkingBlock {
    return block.type === 'thinking';
  }

  isToolCall(block: MessageBlock): block is import('../../../core/models/chat.models').ToolBlock {
    return block.type === 'tool_call';
  }

  isText(block: MessageBlock): block is import('../../../core/models/chat.models').TextBlock {
    return block.type === 'text';
  }

  isError(block: MessageBlock): block is import('../../../core/models/chat.models').ErrorBlock {
    return block.type === 'error';
  }
}
