import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class BreakpointService {
  /** True when the viewport is narrower than Tailwind's `lg` breakpoint (1024 px). */
  readonly isMobile = signal<boolean>(this._check());

  private _mq = window.matchMedia('(max-width: 1023px)');
  private _handler = (e: MediaQueryListEvent) => this.isMobile.set(e.matches);

  constructor() {
    this._mq.addEventListener('change', this._handler);
  }

  private _check(): boolean {
    return window.matchMedia('(max-width: 1023px)').matches;
  }
}
