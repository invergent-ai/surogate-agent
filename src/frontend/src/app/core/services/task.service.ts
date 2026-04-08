import { Injectable, OnDestroy, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, Subject, map, catchError, of } from 'rxjs';
import { ApiConfigService } from './api-config.service';
import { AuthService } from './auth.service';
import { HumanTask, HumanTaskRaw, TaskRespondPayload, mapTask } from '../models/task.models';

@Injectable({ providedIn: 'root' })
export class TaskService implements OnDestroy {
  private http   = inject(HttpClient);
  private config = inject(ApiConfigService);
  private auth   = inject(AuthService);

  /** All tasks currently assigned to the logged-in user. */
  assignedTasks = signal<HumanTask[]>([]);

  /** All tasks sent by the logged-in user. */
  originatedTasks = signal<HumanTask[]>([]);

  /** Pending tasks count (badge). */
  pendingCount = computed(() =>
    this.assignedTasks().filter(t => t.status === 'pending').length
  );

  /** Emits session_ids when the backend reports agent continuation is ready. */
  readonly sessionResumed$ = new Subject<string>();

  private _notifController: AbortController | null = null;
  private _pollTimer: ReturnType<typeof setTimeout> | null = null;

  private url(path = ''): string {
    return `${this.config.apiUrl}/tasks${path}`;
  }

  // ── Task list ──────────────────────────────────────────────────────────────

  listAssigned(status = 'all'): Observable<HumanTask[]> {
    return this.http
      .get<HumanTaskRaw[]>(this.url(`?role=assigned&status=${status}`))
      .pipe(map(list => list.map(mapTask)), catchError(() => of([])));
  }

  listOriginated(status = 'all'): Observable<HumanTask[]> {
    return this.http
      .get<HumanTaskRaw[]>(this.url(`?role=originated&status=${status}`))
      .pipe(map(list => list.map(mapTask)), catchError(() => of([])));
  }

  getTask(id: string): Observable<HumanTask> {
    return this.http
      .get<HumanTaskRaw>(this.url(`/${id}`))
      .pipe(map(mapTask));
  }

  respond(id: string, payload: TaskRespondPayload): Observable<void> {
    return this.http.post<void>(this.url(`/${id}/respond`), payload);
  }

  cancel(id: string): Observable<void> {
    return this.http.delete<void>(this.url(`/${id}`));
  }

  uploadTaskFiles(id: string, files: File[]): Observable<{ ok: boolean; files: string[] }> {
    const form = new FormData();
    for (const f of files) {
      form.append('files', f, f.name);
    }
    return this.http.post<{ ok: boolean; files: string[] }>(this.url(`/${id}/upload`), form);
  }

  // ── Polling refresh ────────────────────────────────────────────────────────

  /** Refresh both assigned and originated task lists. */
  refresh(): void {
    this.listAssigned('all').subscribe(tasks => this.assignedTasks.set(tasks));
    this.listOriginated('all').subscribe(tasks => this.originatedTasks.set(tasks));
  }

  // ── SSE notifications ──────────────────────────────────────────────────────

  /**
   * Open an SSE connection to /tasks/notifications.
   * Emits a ``new_task`` event when the backend detects a newly assigned task.
   * Automatically refreshes ``assignedTasks`` on each new event.
   */
  startNotifications(): void {
    if (this._notifController) return; // already running

    const token = this.auth.token();
    if (!token) return;

    this._notifController = new AbortController();
    const url = this.url('/notifications');
    const signal = this._notifController.signal;

    const connect = async () => {
      try {
        const resp = await fetch(url, {
          method: 'GET',
          headers: { Authorization: `Bearer ${token}` },
          signal,
        });

        if (!resp.ok || !resp.body) return;

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done || signal.aborted) break;
          const text = decoder.decode(value, { stream: true });
          // Parse SSE lines
          const lines = text.split('\n');
          for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (line.startsWith('event: new_task')) {
              // Refresh task list on any new task notification
              this.refresh();
            } else if (line.startsWith('event: session_resumed')) {
              // Find the data line immediately following
              const dataLine = lines[i + 1] ?? '';
              if (dataLine.startsWith('data:')) {
                try {
                  const payload = JSON.parse(dataLine.slice(5).trim());
                  if (payload.session_id) {
                    this.sessionResumed$.next(payload.session_id);
                  }
                } catch { /* ignore parse errors */ }
              }
            }
          }
        }
        // Stream ended normally (server closed) — reconnect unless stopped
        if (!signal.aborted) {
          this._pollTimer = setTimeout(() => connect(), 1000);
        }
      } catch {
        // Connection failed or aborted — reconnect after delay unless stopped
        if (!signal.aborted) {
          this._pollTimer = setTimeout(() => connect(), 3000);
        }
      }
    };

    // Do an initial refresh immediately, then connect SSE
    this.refresh();
    connect();
  }

  stopNotifications(): void {
    if (this._notifController) {
      this._notifController.abort();
      this._notifController = null;
    }
    if (this._pollTimer) {
      clearTimeout(this._pollTimer);
      this._pollTimer = null;
    }
  }

  ngOnDestroy(): void {
    this.stopNotifications();
  }
}
