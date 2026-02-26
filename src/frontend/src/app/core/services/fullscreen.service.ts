import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class FullscreenService {
  readonly active = signal(false);

  open()  { this.active.set(true);  }
  close() { this.active.set(false); }
}
