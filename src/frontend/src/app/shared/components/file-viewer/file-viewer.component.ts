import { Component, Input, Output, EventEmitter, signal, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-file-viewer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './file-viewer.component.html',
})
export class FileViewerComponent implements OnChanges {
  @Input() content = '';
  @Input() fileName = '';
  @Input() readOnly = false;
  @Output() saved = new EventEmitter<string>();

  editedContent = signal('');
  dirty = signal(false);

  ngOnChanges() {
    this.editedContent.set(this.content);
    this.dirty.set(false);
  }

  onInput(value: string) {
    this.editedContent.set(value);
    this.dirty.set(value !== this.content);
  }

  save() {
    this.saved.emit(this.editedContent());
    this.dirty.set(false);
  }

  reset() {
    this.editedContent.set(this.content);
    this.dirty.set(false);
  }
}
