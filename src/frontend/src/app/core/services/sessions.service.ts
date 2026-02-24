import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, of } from 'rxjs';
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
    form.append('upload', file, file.name); // 'upload' matches the FastAPI UploadFile param name
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
}
