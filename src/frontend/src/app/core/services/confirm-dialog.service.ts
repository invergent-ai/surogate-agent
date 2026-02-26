import { Injectable, signal } from '@angular/core';

export interface ConfirmOptions {
  title: string;
  message: string;
  actionLabel: string;
}

interface PendingDialog extends ConfirmOptions {
  resolve: (confirmed: boolean) => void;
}

@Injectable({ providedIn: 'root' })
export class ConfirmDialogService {
  readonly pending = signal<PendingDialog | null>(null);

  /**
   * Show a confirmation overlay and return a Promise that resolves to true
   * when the user confirms, or false when they cancel / dismiss.
   */
  confirm(message: string, opts?: Partial<ConfirmOptions>): Promise<boolean> {
    return new Promise(resolve => {
      this.pending.set({
        title:       opts?.title       ?? 'Confirm deletion',
        message,
        actionLabel: opts?.actionLabel ?? 'Delete',
        resolve,
      });
    });
  }

  /** Called by the dialog component when the user makes a choice. */
  resolve(confirmed: boolean): void {
    const dialog = this.pending();
    this.pending.set(null);
    dialog?.resolve(confirmed);
  }
}
