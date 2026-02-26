import {
  Component, Input, Output, EventEmitter, signal, ViewChild, ElementRef
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SessionMeta } from '../../../core/models/session.models';

@Component({
  selector: 'app-sessions-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './sessions-list.component.html',
})
export class SessionsListComponent {
  @ViewChild('editInput') editInputRef?: ElementRef<HTMLInputElement>;

  @Input() sessions: SessionMeta[] = [];
  @Input() activeSessionId = '';

  @Output() sessionSelected      = new EventEmitter<SessionMeta>();
  @Output() sessionDeleted       = new EventEmitter<string>();
  @Output() sessionRenamed       = new EventEmitter<{ sessionId: string; name: string }>();
  @Output() newSessionRequested  = new EventEmitter<void>();

  editingId   = signal<string | null>(null);
  editingName = signal('');

  startEdit(meta: SessionMeta, e: Event) {
    e.stopPropagation();
    this.editingId.set(meta.sessionId);
    this.editingName.set(meta.name);
    // Focus the input after Angular renders it
    setTimeout(() => this.editInputRef?.nativeElement.select(), 0);
  }

  commitEdit() {
    const id   = this.editingId();
    const name = this.editingName().trim();
    if (id && name) this.sessionRenamed.emit({ sessionId: id, name });
    this.editingId.set(null);
  }

  cancelEdit() {
    this.editingId.set(null);
  }

  onEditKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter')  { e.preventDefault(); this.commitEdit(); }
    if (e.key === 'Escape') { e.preventDefault(); this.cancelEdit(); }
  }

  onDeleteClick(sessionId: string, e: Event) {
    e.stopPropagation();
    this.sessionDeleted.emit(sessionId);
  }

  formatDate(iso: string): string {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / 86_400_000);
    if (diffDays === 0) {
      return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    }
    if (diffDays === 1) return 'yesterday';
    if (diffDays < 7)   return `${diffDays}d ago`;
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  }
}
