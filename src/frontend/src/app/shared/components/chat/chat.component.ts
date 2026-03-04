import {
  Component, Input, Output, EventEmitter, signal, computed,
  ViewChild, ElementRef, OnDestroy, OnChanges, SimpleChanges, effect, inject
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ChatService } from '../../../core/services/chat.service';
import { SessionsService } from '../../../core/services/sessions.service';
import { SettingsService } from '../../../core/services/settings.service';
import { SkillsService } from '../../../core/services/skills.service';
import { ToastService } from '../../../core/services/toast.service';
import {
  ChatMessage, MessageBlock, SseEvent, ToolBlock, ThinkingBlock, SseSkillUseData
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
export class ChatComponent implements OnChanges, OnDestroy {
  @ViewChild('messageList')  private messageListRef!:  ElementRef<HTMLElement>;
  @ViewChild('thinkingList') private thinkingListRef?: ElementRef<HTMLElement>;

  @Input() role: 'developer' | 'user' = 'user';
  @Input() skill = '';
  @Input() sessionId = '';
  @Input() historyKey = '';
  @Input() compact = false;
  @Input() placeholder = 'Type a message…';
  @Input() showSkillActivity = false;

  @Output() sessionCreated    = new EventEmitter<string>();
  @Output() skillDetected     = new EventEmitter<string>();
  @Output() filesChanged      = new EventEmitter<string[]>();
  @Output() settingsRequired  = new EventEmitter<void>();
  /** Emitted with true when the first message is added, false when messages are cleared. */
  @Output() hasMessages       = new EventEmitter<boolean>();
  /** Emitted after each streaming turn completes with the full message list (timestamps serialized to ISO strings). */
  @Output() messagesSnapshot  = new EventEmitter<unknown[]>();

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

  /** Skills announced by the backend for the current turn; drives the skill activity panel. */
  skillActivities = signal<{ name: string; description: string; finished: boolean; startTime: number; endTime?: number }[]>([]);

  // Panel visibility: eye icon toggles show/hide; slashed eye = hidden
  agentPanelHidden  = signal(false);
  skillPanelHidden  = signal(false);

  /** Name of the currently expanded skill item, or null if none. Exclusive — only one open at a time. */
  expandedSkill = signal<string | null>(null);

  /** True when at least one panel has visible content — drives the outer panel height. */
  readonly activityContentVisible = computed(() =>
    (this.thinkingBlocks().length > 0 && !this.agentPanelHidden()) ||
    (this.skillActivities().length > 0 && !this.skillPanelHidden())
  );

  private chatService  = inject(ChatService);
  private sessionsSvc  = inject(SessionsService);
  private settings     = inject(SettingsService);
  private skillsSvc    = inject(SkillsService);
  private toast        = inject(ToastService);

  /** Height of the thinking panel in pixels — user-resizable. */
  thinkingPanelHeight = signal(180);

  /** Descriptions received from skill_use SSE events; used as a lookup when tool_call entries are added. */
  private _skillDescriptions = new Map<string, string>();

  private sub?: Subscription;
  private _currentAssistantId = '';
  private _dragStartY    = 0;
  private _dragStartH    = 0;
  private _boundMouseMove?: (e: MouseEvent) => void;
  private _boundMouseUp?:   () => void;

  // Input history — behaves like a terminal (Up/Down to browse sent messages).
  private readonly HISTORY_LIMIT = 50;
  private _sentHistory: string[] = [];
  private _historyIndex = -1;   // -1 = not browsing (showing draft)
  private _draftText    = '';   // saved draft while browsing history

  onDividerMouseDown(e: MouseEvent) {
    e.preventDefault();
    this._dragStartY = e.clientY;
    this._dragStartH = this.thinkingPanelHeight();

    this._boundMouseMove = (ev: MouseEvent) => {
      const h = Math.max(60, Math.min(520, this._dragStartH + ev.clientY - this._dragStartY));
      this.thinkingPanelHeight.set(h);
    };
    this._boundMouseUp = () => {
      document.removeEventListener('mousemove', this._boundMouseMove!);
      document.removeEventListener('mouseup',   this._boundMouseUp!);
    };
    document.addEventListener('mousemove', this._boundMouseMove);
    document.addEventListener('mouseup',   this._boundMouseUp);
  }

  constructor() {
    effect(() => {
      // Keep sessionId in sync when parent updates it
      if (this.sessionId) this.currentSessionId.set(this.sessionId);
    });
    effect(() => {
      this.hasMessages.emit(this.messages().length > 0);
    });
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['historyKey']) {
      const key = changes['historyKey'].currentValue as string;
      this.inputText.set('');
      this._historyIndex = -1;
      this._draftText = '';
      if (key) {
        this.sessionsSvc.getInputHistory(key).subscribe(entries => {
          this._sentHistory = entries;
        });
      } else {
        this._sentHistory = [];
      }
    }
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

    // Append to history, skip exact duplicate of the last entry.
    if (!this._sentHistory.length || this._sentHistory[this._sentHistory.length - 1] !== text) {
      this._sentHistory.push(text);
      if (this._sentHistory.length > this.HISTORY_LIMIT) this._sentHistory.shift();
    }
    this._historyIndex = -1;
    this._draftText    = '';

    if (this.historyKey) {
      this.sessionsSvc.saveInputHistory(this.historyKey, this._sentHistory).subscribe();
    }

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
    this.expandedSkill.set(null);
    this.messages.update(msgs => [
      ...msgs,
      { id: nextId(), role: 'user', blocks: [{ type: 'text', text }], timestamp: new Date(), finalized: true },
    ]);

    const assistantId = nextId();
    this.messages.update(msgs => [
      ...msgs,
      { id: assistantId, role: 'assistant', blocks: [], timestamp: new Date(), finalized: false },
    ]);

    this._currentAssistantId = assistantId;
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
        this.skillActivities.update(list => list.map(s => ({ ...s, finished: true, endTime: s.endTime ?? Date.now() })));
        this.streaming.set(false);
      },
      complete: () => {
        this._currentAssistantId = '';
        this.streaming.set(false);
        this._emitSnapshot();
      },
    });
  }

  stop() {
    this.sub?.unsubscribe();
    this.sub = undefined;
    if (this._currentAssistantId) {
      this.finalizeAssistant(this._currentAssistantId, []);
      this._currentAssistantId = '';
    }
    this.skillActivities.update(list => list.map(s => ({ ...s, finished: true, endTime: s.endTime ?? Date.now() })));
    this.streaming.set(false);
    this._emitSnapshot();
  }

  private _emitSnapshot() {
    const snapshot = this.messages().map(m => ({
      ...m,
      timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : m.timestamp,
    }));
    if (snapshot.length > 0) this.messagesSnapshot.emit(snapshot);
  }

  private handleEvent(ev: SseEvent, assistantId: string) {
    // skill_use announces which skills are loaded — store the description for
    // later lookup but don't add to the activity list yet. Entries appear only
    // when the agent actually reads a SKILL.md file (tool_call below).
    if (ev.event === 'skill_use') {
      const d = ev.data as SseSkillUseData;
      this._skillDescriptions.set(d.name, d.description);
      return;
    }

    // Mark all skills finished when the turn completes or errors
    if (ev.event === 'done' || ev.event === 'error') {
      this.skillActivities.update(list => list.map(s => ({ ...s, finished: true, endTime: s.endTime ?? Date.now() })));
    }

    // Each time the agent reads a SKILL.md file, add a new activity entry —
    // duplicates are intentional (ordered execution history, not a unique set).
    if (ev.event === 'tool_call' && this.showSkillActivity) {
      const path = (ev.data.args?.['path'] ?? ev.data.args?.['file_path'] ?? '') as string;
      const m = path.match(SKILL_PATH_RE);
      const skillName = m
        ? m[1]
        : (/(?:^|[/\\])SKILL\.md$/i.test(path) && this.skill) ? this.skill : null;
      if (skillName) {
        this.skillActivities.update(list => [
          ...list,
          { name: skillName, description: this._skillDescriptions.get(skillName) ?? '', finished: false, startTime: Date.now() },
        ]);
      }
    }

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
    this.skillActivities.set([]);
    this.expandedSkill.set(null);
    // Generate a fresh ID so the backend opens a new LangGraph thread rather
    // than resuming the old checkpoint — prevents stale context after a skill switch.
    const freshId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    this.currentSessionId.set(freshId);
  }

  /** Restore a previously saved session: replay messages and set the session ID. */
  restoreSession(msgs: ChatMessage[], sessionId: string) {
    // Always reset transient state so switching to a new/empty session starts clean.
    this.skillActivities.set([]);
    this.expandedSkill.set(null);

    // Advance msgCounter past any IDs already in the restored list so that
    // the first nextId() call after restore never collides with a restored
    // message ID.  Without this, handleEvent() finds the wrong (old) bubble
    // and writes the new response onto it while the new bubble stays empty.
    for (const m of msgs) {
      const n = parseInt(m.id.replace('msg-', ''), 10);
      if (!isNaN(n) && n > msgCounter) msgCounter = n;
    }
    this.messages.set(msgs.map(m => ({
      ...m,
      timestamp: m.timestamp instanceof Date ? m.timestamp : new Date(m.timestamp as unknown as string),
    })));
    this.currentSessionId.set(sessionId);

    // Re-populate skill activity panel from tool_call blocks in the restored messages.
    // Skill_use SSE events aren't replayed on restore, so we derive skill names from
    // any SKILL.md paths that appear in saved tool_call args.
    if (this.showSkillActivity) {
      const seen = new Set<string>();
      const skills: { name: string; description: string; finished: boolean; startTime: number; endTime?: number }[] = [];
      const now = Date.now();
      for (const msg of msgs) {
        for (const block of msg.blocks) {
          if (block.type === 'tool_call') {
            const path = ((block as ToolBlock).args?.['path'] ?? (block as ToolBlock).args?.['file_path'] ?? '') as string;
            const m = path.match(SKILL_PATH_RE);
            if (m && !seen.has(m[1])) {
              seen.add(m[1]);
              skills.push({ name: m[1], description: '', finished: true, startTime: now });
            }
          }
        }
      }
      if (skills.length > 0) {
        this.skillActivities.set(skills);
        // Fetch descriptions from the skills API and patch them in
        this.skillsSvc.list('user').subscribe({
          next: (allSkills) => {
            const descMap = new Map(allSkills.map(s => [s.name, s.description]));
            this.skillActivities.update(list =>
              list.map(s => ({ ...s, description: descMap.get(s.name) ?? s.description }))
            );
          },
          error: () => { /* keep skills without descriptions on API failure */ },
        });
      }
    }
  }

  onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.send(); return; }

    if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
      const ta = e.target as HTMLTextAreaElement;
      const goBack = e.key === 'ArrowUp';

      // Only intercept when the cursor is on the first (Up) or last (Down) line
      // so normal multi-line caret movement is unaffected.
      const beforeCursor = ta.value.substring(0, ta.selectionStart);
      const afterCursor  = ta.value.substring(ta.selectionStart);
      const onFirstLine  = !beforeCursor.includes('\n');
      const onLastLine   = !afterCursor.includes('\n');

      if (goBack && onFirstLine && this._sentHistory.length) {
        e.preventDefault();
        if (this._historyIndex === -1) this._draftText = this.inputText();
        this._historyIndex = this._historyIndex === -1
          ? this._sentHistory.length - 1
          : Math.max(0, this._historyIndex - 1);
        this._applyHistory();
      } else if (!goBack && this._historyIndex !== -1 && onLastLine) {
        e.preventDefault();
        const next = this._historyIndex + 1;
        if (next >= this._sentHistory.length) {
          this._historyIndex = -1;
          this.inputText.set(this._draftText);
        } else {
          this._historyIndex = next;
          this._applyHistory();
        }
      }
    }
  }

  private _applyHistory() {
    this.inputText.set(this._sentHistory[this._historyIndex]);
    // Move caret to end on next tick (after Angular updates the DOM value).
    setTimeout(() => {
      const ta = document.activeElement as HTMLTextAreaElement | null;
      if (ta?.tagName === 'TEXTAREA') ta.setSelectionRange(ta.value.length, ta.value.length);
    }, 0);
  }

  toggleAgentPanel() { this.agentPanelHidden.update(v => !v); }
  toggleSkillPanel() { this.skillPanelHidden.update(v => !v); }

  /** CSS classes for the agent activity column — adjusts width based on both panels' visibility. */
  getAgentColumnClass(): string {
    const skillVisible = this.showSkillActivity && this.skillActivities().length > 0 && !this.skillPanelHidden();
    if (this.agentPanelHidden()) {
      return 'flex-none' + (skillVisible ? ' border-r border-gray-200 dark:border-zinc-700' : '');
    }
    if (skillVisible) return 'w-3/4 flex-none border-r border-gray-200 dark:border-zinc-700';
    return 'flex-1';
  }

  /** CSS classes for the skill activity column — adjusts width based on both panels' visibility. */
  getSkillColumnClass(): string {
    const agentVisible = this.thinkingBlocks().length > 0 && !this.agentPanelHidden();
    if (this.skillPanelHidden()) {
      return agentVisible ? 'flex-none border-l border-gray-200 dark:border-zinc-700' : 'flex-none';
    }
    if (agentVisible) return 'w-1/4 flex-none';
    return 'flex-1';
  }

  toggleSkillExpanded(name: string) {
    this.expandedSkill.update(current => current === name ? null : name);
  }

  formatDuration(startTime: number, endTime?: number): string {
    const ms = (endTime ?? Date.now()) - startTime;
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  private scrollToBottom() {
    setTimeout(() => {
      const ml = this.messageListRef?.nativeElement;
      if (ml) ml.scrollTop = ml.scrollHeight;
      const tl = this.thinkingListRef?.nativeElement;
      if (tl) tl.scrollTop = tl.scrollHeight;
    }, 0);
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
    if (this._boundMouseMove) document.removeEventListener('mousemove', this._boundMouseMove);
    if (this._boundMouseUp)   document.removeEventListener('mouseup',   this._boundMouseUp);
  }
}
