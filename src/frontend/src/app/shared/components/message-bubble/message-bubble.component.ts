import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatMessage, MessageBlock, TextBlock, ErrorBlock, ImageBlock, HitlResponseBlock } from '../../../core/models/chat.models';
import { MarkdownContentComponent } from '../markdown-content/markdown-content.component';

@Component({
  selector: 'app-message-bubble',
  standalone: true,
  imports: [CommonModule, MarkdownContentComponent],
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

  isImage(block: MessageBlock): block is ImageBlock {
    return block.type === 'image';
  }

  isHitlResponse(block: MessageBlock): block is HitlResponseBlock {
    return block.type === 'hitl_response';
  }

  hasTextOrError(): boolean {
    return this.message.blocks.some(b => b.type === 'text' || b.type === 'error');
  }

  downloadImage(block: ImageBlock) {
    const a = document.createElement('a');
    a.href = block.dataUrl;
    a.download = block.fileName ?? 'image.png';
    a.click();
  }

  /**
   * While streaming: a text block is intermediary the instant another block
   * arrives after it (i.e. it is no longer the last item in the array).
   * This is detectable purely from the array length — no need to wait for a
   * separate flag to be written.
   *
   * After finalized: fall back to the explicit `intermediary` flag that was
   * stamped on the block when the following tool_call arrived, so only true
   * intermediary blocks keep the frame (the final text loses it and gets
   * the toolbar instead).
   */
  isIntermediaryText(block: MessageBlock): boolean {
    if (block.type !== 'text') return false;
    // After finalized: only blocks explicitly stamped by the tool_call handler keep the frame.
    if (this.message.finalized) return !!(block as TextBlock).intermediary;
    // While streaming: every text block is in-progress — we don't know yet which
    // will be the final answer, so frame them all immediately.
    return true;
  }
}
