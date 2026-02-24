import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatMessage, MessageBlock, TextBlock, ErrorBlock } from '../../../core/models/chat.models';

@Component({
  selector: 'app-message-bubble',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './message-bubble.component.html',
})
export class MessageBubbleComponent {
  @Input({ required: true }) message!: ChatMessage;

  isText(block: MessageBlock): block is TextBlock {
    return block.type === 'text';
  }

  isError(block: MessageBlock): block is ErrorBlock {
    return block.type === 'error';
  }
}
