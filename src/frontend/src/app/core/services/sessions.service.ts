import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of } from 'rxjs';
import { ApiConfigService } from './api-config.service';
import {
  ChatHistoryResponse,
  FileInfo,
  SessionMeta,
  SessionMetaResponse,
  SessionResponse,
} from '../models/session.models';

@Injectable({ providedIn: 'root' })
export class SessionsService {
  constructor(private http: HttpClient, private config: ApiConfigService) {}

  private url(path = ''): string {
    return `${this.config.apiUrl}/sessions${path}`;
  }

  // ── Session workspace endpoints ─────────────────────────────────────────

  list(): Observable<SessionResponse[]> {
    return this.http.get<SessionResponse[]>(this.url());
  }

  get(sessionId: string): Observable<SessionResponse> {
    return this.http.get<SessionResponse>(this.url(`/${sessionId}`));
  }

  delete(sessionId: string): Observable<{ deleted: string }> {
    return this.http.delete<{ deleted: string }>(this.url(`/${sessionId}`));
  }

  listFiles(sessionId: string): Observable<FileInfo[]> {
    return this.http.get<FileInfo[]>(this.url(`/${sessionId}/files`)).pipe(
      catchError(() => of([]))
    );
  }

  downloadFile(sessionId: string, fileName: string): Observable<Blob> {
    return this.http.get(this.url(`/${sessionId}/files/${encodeURIComponent(fileName)}`), { responseType: 'blob' });
  }

  readFile(sessionId: string, fileName: string): Observable<string> {
    return this.http.get(this.url(`/${sessionId}/files/${encodeURIComponent(fileName)}`), { responseType: 'text' });
  }

  uploadFile(sessionId: string, file: File): Observable<unknown> {
    const form = new FormData();
    form.append('upload', file, file.name);
    return this.http.post(this.url(`/${sessionId}/files`), form, {
      params: { filename: file.name },
    });
  }

  saveTextFile(sessionId: string, fileName: string, content: string): Observable<unknown> {
    const blob = new Blob([content], { type: 'text/plain' });
    const file = new File([blob], fileName);
    return this.uploadFile(sessionId, file);
  }

  deleteFile(sessionId: string, fileName: string): Observable<{ deleted: string }> {
    return this.http.delete<{ deleted: string }>(this.url(`/${sessionId}/files/${encodeURIComponent(fileName)}`));
  }

  // ── Session metadata endpoints ──────────────────────────────────────────

  /** List all sessions owned by the current user, ordered newest-first. */
  listMeta(): Observable<SessionMeta[]> {
    return this.http.get<SessionMetaResponse[]>(this.url('/meta')).pipe(
      map(rs => rs.map(r => ({ sessionId: r.session_id, name: r.name, createdAt: r.created_at }))),
      catchError(() => of([])),
    );
  }

  /** Create (or return existing) session metadata. */
  createMeta(sessionId: string, name: string): Observable<SessionMeta> {
    return this.http
      .post<SessionMetaResponse>(this.url('/meta'), { session_id: sessionId, name })
      .pipe(map(r => ({ sessionId: r.session_id, name: r.name, createdAt: r.created_at })));
  }

  /** Rename a session. */
  updateMeta(sessionId: string, name: string): Observable<SessionMeta> {
    return this.http
      .patch<SessionMetaResponse>(this.url(`/meta/${sessionId}`), { name })
      .pipe(map(r => ({ sessionId: r.session_id, name: r.name, createdAt: r.created_at })));
  }

  /** Delete session metadata + chat history from the DB. */
  deleteMeta(sessionId: string): Observable<unknown> {
    return this.http.delete(this.url(`/meta/${sessionId}`));
  }

  // ── Chat history endpoints ───────────────────────────────────────────────

  /** Load previously saved chat messages for a session. */
  getHistory(sessionId: string): Observable<ChatHistoryResponse> {
    return this.http.get<ChatHistoryResponse>(this.url(`/${sessionId}/history`)).pipe(
      catchError(() => of({ session_id: sessionId, messages: [] })),
    );
  }

  /** Save (upsert) chat messages for a session. */
  saveHistory(sessionId: string, messages: unknown[]): Observable<unknown> {
    return this.http.put(this.url(`/${sessionId}/history`), { messages }).pipe(
      catchError(() => of(null)),
    );
  }
}
