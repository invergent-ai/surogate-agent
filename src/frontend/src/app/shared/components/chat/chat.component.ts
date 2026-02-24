import {
  Component, Input, Output, EventEmitter, signal, computed,
  ViewChild, ElementRef, OnDestroy, effect, inject
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ChatService } from '../../../core/services/chat.service';
import { SettingsService } from '../../../core/services/settings.service';
import { ToastService } from '../../../core/services/toast.service';
import {
  ChatMessage, MessageBlock, SseEvent, ToolBlock, ThinkingBlock
} from '../../../core/models/chat.models';
import { MessageBubbleComponent } from '../message-bubble/message-bubble.component';
import { ThinkingBlockComponent } from '../thinking-block/thinking-block.component';
import { ToolCallBlockComponent } from '../tool-call-block/tool-call-block.component';

let msgCounter = 0;
function nextId() { return `msg-${++msgCounter}`; }

// Regex to extract skill name from paths like "skills/foo/SKILL.md"
const SKILL_PATH_RE = /skills\/([^/]+)\/SKILL\.md/;

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, MessageBubbleComponent, ThinkingBlockComponent, ToolCallBlockComponent],
  templateUrl: './chat.component.html',
})
export class ChatComponent implements OnDestroy {
  @ViewChild('messageList')  private messageListRef!:  ElementRef<HTMLElement>;
  @ViewChild('thinkingList') private thinkingListRef?: ElementRef<HTMLElement>;

  @Input() role: 'developer' | 'user' = 'user';
  @Input() skill = '';
  @Input() sessionId = '';
  @Input() compact = false;
  @Input() placeholder = 'Type a message…';

  @Output() sessionCreated   = new EventEmitter<string>();
  @Output() skillDetected    = new EventEmitter<string>();
  @Output() filesChanged     = new EventEmitter<string[]>();
  /** Emitted when chat is attempted but model/API key are not configured. */
  @Output() settingsRequired = new EventEmitter<void>();

  messages = signal<ChatMessage[]>([]);
  streaming = signal(false);
  currentSessionId = signal('');
  inputText = signal('');

  /** All thinking + tool_call blocks extracted from assistant messages for the side panel. */
  readonly thinkingBlocks = computed<(ThinkingBlock | ToolBlock)[]>(() => {
    const result: (ThinkingBlock | ToolBlock)[] = [];
    for (const msg of this.messages()) {
      if (msg.role !== 'assistant') continue;
      for (const block of msg.blocks) {
        if (block.type === 'thinking' || block.type === 'tool_call') {
          result.push(block as ThinkingBlock | ToolBlock);
        }
      }
    }
    return result;
  });

  private chatService = inject(ChatService);
  private settings    = inject(SettingsService);
  private toast       = inject(ToastService);

  private sub?: Subscription;

  constructor() {
    effect(() => {
      // Keep sessionId in sync when parent updates it
      if (this.sessionId) this.currentSessionId.set(this.sessionId);
    });
  }

  isThinkingBlock(block: ThinkingBlock | ToolBlock): block is ThinkingBlock {
    return block.type === 'thinking';
  }

  isToolBlock(block: ThinkingBlock | ToolBlock): block is ToolBlock {
    return block.type === 'tool_call';
  }

  hasVisibleContent(msg: ChatMessage): boolean {
    return msg.role === 'user'
      || !msg.finalized
      || msg.blocks.some(b => b.type === 'text' || b.type === 'error');
  }

  send() {
    const text = this.inputText().trim();
    if (!text || this.streaming()) return;

    // Guard: settings must be configured before chatting
    if (!this.settings.isConfigured()) {
      this.toast.warning(
        'Model and API key are required. Open ⚙ Settings to configure.',
        { label: 'Open Settings', callback: () => this.settingsRequired.emit() }
      );
      this.settingsRequired.emit();
      return;
    }

    this.inputText.set('');
    this.messages.update(msgs => [
      ...msgs,
      { id: nextId(), role: 'user', blocks: [{ type: 'text', text }], timestamp: new Date(), finalized: true },
    ]);

    const assistantId = nextId();
    this.messages.update(msgs => [
      ...msgs,
      { id: assistantId, role: 'assistant', blocks: [], timestamp: new Date(), finalized: false },
    ]);

    this.streaming.set(true);
    this.scrollToBottom();

    this.sub = this.chatService.streamChat({
      message: text,
      role: this.role,
      session_id: this.currentSessionId() || undefined,
      skill: this.skill || undefined,
    }).subscribe({
      next: (ev: SseEvent) => this.handleEvent(ev, assistantId),
      error: (err) => {
        this.finalizeAssistant(assistantId, [{ type: 'error', text: String(err?.message ?? err) }]);
        this.streaming.set(false);
      },
      complete: () => this.streaming.set(false),
    });
  }

  private handleEvent(ev: SseEvent, assistantId: string) {
    this.messages.update(msgs => {
      const idx = msgs.findIndex(m => m.id === assistantId);
      if (idx < 0) return msgs;
      const copy = [...msgs];
      const msg = { ...copy[idx], blocks: [...copy[idx].blocks] };

      switch (ev.event) {
        case 'thinking':
          msg.blocks.push({ type: 'thinking', text: ev.data.text, collapsed: true });
          break;
        case 'tool_call': {
          const tc: ToolBlock = { type: 'tool_call', name: ev.data.name, args: ev.data.args, collapsed: true };
          msg.blocks.push(tc);
          // Detect skill from write_file calls
          const path = (ev.data.args?.['path'] ?? ev.data.args?.['file_path'] ?? '') as string;
          const m = path.match(SKILL_PATH_RE);
          if (m) this.skillDetected.emit(m[1]);
          break;
        }
        case 'tool_result': {
          // Attach result to last matching tool_call block
          const tcIdx = [...msg.blocks].reverse().findIndex(
            b => b.type === 'tool_call' && (b as ToolBlock).name === ev.data.name && !(b as ToolBlock).result
          );
          if (tcIdx >= 0) {
            const realIdx = msg.blocks.length - 1 - tcIdx;
            (msg.blocks[realIdx] as ToolBlock).result = ev.data.result;
          }
          break;
        }
        case 'text':
          // Append to last text block or create new one
          if (msg.blocks.length > 0 && msg.blocks[msg.blocks.length - 1].type === 'text') {
            (msg.blocks[msg.blocks.length - 1] as { text: string }).text += ev.data.text;
          } else {
            msg.blocks.push({ type: 'text', text: ev.data.text });
          }
          break;
        case 'done':
          msg.finalized = true;
          if (ev.data.session_id) {
            const sid = ev.data.session_id;
            if (!this.currentSessionId()) {
              this.currentSessionId.set(sid);
              this.sessionCreated.emit(sid);
            }
          }
          if (ev.data.files?.length) this.filesChanged.emit(ev.data.files);
          break;
        case 'error':
          msg.blocks.push({ type: 'error', text: ev.data.detail });
          msg.finalized = true;
          break;
      }

      copy[idx] = msg;
      return copy;
    });
    this.scrollToBottom();
  }

  private finalizeAssistant(id: string, extraBlocks: MessageBlock[]) {
    this.messages.update(msgs => {
      const idx = msgs.findIndex(m => m.id === id);
      if (idx < 0) return msgs;
      const copy = [...msgs];
      copy[idx] = { ...copy[idx], blocks: [...copy[idx].blocks, ...extraBlocks], finalized: true };
      return copy;
    });
  }

  clearMessages() {
    this.messages.set([]);
    this.currentSessionId.set('');
  }

  onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.send(); }
  }

  private scrollToBottom() {
    setTimeout(() => {
      const ml = this.messageListRef?.nativeElement;
      if (ml) ml.scrollTop = ml.scrollHeight;
      const tl = this.thinkingListRef?.nativeElement;
      if (tl) tl.scrollTop = tl.scrollHeight;
    }, 0);
  }

  ngOnDestroy() { this.sub?.unsubscribe(); }
}
