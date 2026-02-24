import { Injectable, signal } from '@angular/core';

export type ToastType = 'warning' | 'error' | 'success' | 'info';

export interface Toast {
  id: number;
  type: ToastType;
  message: string;
  action?: { label: string; callback: () => void };
  duration: number;
}

let _id = 0;

@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly toasts = signal<Toast[]>([]);

  show(
    type: ToastType,
    message: string,
    options?: { action?: Toast['action']; duration?: number }
  ): void {
    const id = ++_id;
    const duration = options?.duration ?? 5000;
    this.toasts.update(list => [...list, { id, type, message, action: options?.action, duration }]);
    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }
  }

  dismiss(id: number): void {
    this.toasts.update(list => list.filter(t => t.id !== id));
  }

  warning(message: string, action?: Toast['action']): void {
    this.show('warning', message, { action });
  }

  error(message: string): void {
    this.show('error', message);
  }

  success(message: string): void {
    this.show('success', message, { duration: 3000 });
  }
}
