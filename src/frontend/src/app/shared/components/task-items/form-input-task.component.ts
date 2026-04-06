import {
  Component, Input, Output, EventEmitter, inject, signal,
  ViewChild, ElementRef, OnChanges, OnDestroy, SimpleChanges,
  AfterViewInit,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { TaskService } from '../../../core/services/task.service';
import { HumanTask } from '../../../core/models/task.models';

@Component({
  selector: 'app-form-input-task',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="flex flex-col gap-3">

      @if (task.description) {
        <p class="text-sm text-gray-600 dark:text-zinc-400 leading-relaxed">{{ task.description }}</p>
      }

      @if (schemaError()) {
        <div class="text-sm text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2">
          {{ schemaError() }}
        </div>
      }

      <!-- Formio render target -->
      <div #formContainer class="formio-wrapper"></div>

      @if (!previewMode && !schemaError()) {
        <button
          (click)="submit()"
          [disabled]="submitting()"
          class="w-full py-2 px-3 rounded-lg text-sm font-medium bg-violet-500 hover:bg-violet-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ submitting() ? 'Submitting…' : 'Submit' }}
        </button>
      }

    </div>
  `,
})
export class FormInputTaskComponent implements OnChanges, AfterViewInit, OnDestroy {
  @Input({ required: true }) task!: HumanTask;
  /** When true, renders the form for preview only — no submit button, no data collection. */
  @Input() previewMode = false;
  @Output() responded = new EventEmitter<void>();

  @ViewChild('formContainer') formContainer!: ElementRef<HTMLDivElement>;

  private taskSvc = inject(TaskService);

  submitting  = signal(false);
  schemaError = signal<string | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private _formInstance: any = null;
  private _viewReady = false;

  ngAfterViewInit(): void {
    this._viewReady = true;
    this._renderForm();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['task'] && this._viewReady) {
      this._destroyForm();
      this._renderForm();
    }
  }

  ngOnDestroy(): void {
    this._destroyForm();
  }

  private _schema(): object | null {
    const raw = this.task?.context?.['_form_schema'];
    if (!raw) return null;
    if (typeof raw === 'object') return raw as object;
    try { return JSON.parse(raw as string); } catch { return null; }
  }

  private _renderForm(): void {
    this.schemaError.set(null);
    const el = this.formContainer?.nativeElement;
    if (!el) return;

    const schema = this._schema();
    if (!schema) {
      this.schemaError.set('No form schema found in task context.');
      return;
    }

    import('formiojs').then(({ Formio }) => {
      Formio.createForm(el, schema, {
        noDefaultSubmitButton: true,
        readOnly: this.previewMode,
      }).then((form: any) => {
        this._formInstance = form;
      }).catch((err: unknown) => {
        this.schemaError.set(`Could not render form: ${err}`);
      });
    }).catch(() => {
      this.schemaError.set('Failed to load form renderer.');
    });
  }

  private _destroyForm(): void {
    if (this._formInstance) {
      try { this._formInstance.destroy(); } catch { /* ignore */ }
      this._formInstance = null;
    }
    if (this.formContainer?.nativeElement) {
      this.formContainer.nativeElement.innerHTML = '';
    }
  }

  submit(): void {
    if (!this._formInstance) return;
    this.submitting.set(true);

    this._formInstance.submit().then((submission: any) => {
      const formData = submission?.data ?? {};
      this.taskSvc.respond(this.task.id, { form_data: formData } as any).subscribe({
        next: () => {
          this.submitting.set(false);
          this.responded.emit();
          this.taskSvc.refresh();
        },
        error: () => this.submitting.set(false),
      });
    }).catch(() => {
      // Validation errors — formio highlights fields automatically
      this.submitting.set(false);
    });
  }
}
