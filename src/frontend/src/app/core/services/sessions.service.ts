import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiConfigService } from './api-config.service';
import { FileInfo, SessionResponse } from '../models/session.models';

@Injectable({ providedIn: 'root' })
export class SessionsService {
  constructor(private http: HttpClient, private config: ApiConfigService) {}

  private url(path = ''): string {
    return `${this.config.apiUrl}/sessions${path}`;
  }

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
    return this.http.get<FileInfo[]>(this.url(`/${sessionId}/files`));
  }

  downloadFile(sessionId: string, fileName: string): Observable<Blob> {
    return this.http.get(this.url(`/${sessionId}/files/${fileName}`), { responseType: 'blob' });
  }

  uploadFile(sessionId: string, file: File): Observable<unknown> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.http.post(this.url(`/${sessionId}/files`), form, {
      params: { filename: file.name },
    });
  }

  deleteFile(sessionId: string, fileName: string): Observable<{ deleted: string }> {
    return this.http.delete<{ deleted: string }>(this.url(`/${sessionId}/files/${fileName}`));
  }
}
