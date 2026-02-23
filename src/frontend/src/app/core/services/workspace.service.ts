import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiConfigService } from './api-config.service';
import { FileInfo, WorkspaceResponse } from '../models/session.models';

@Injectable({ providedIn: 'root' })
export class WorkspaceService {
  constructor(private http: HttpClient, private config: ApiConfigService) {}

  private url(path = ''): string {
    return `${this.config.apiUrl}/workspace${path}`;
  }

  list(): Observable<WorkspaceResponse[]> {
    return this.http.get<WorkspaceResponse[]>(this.url());
  }

  get(skill: string): Observable<WorkspaceResponse> {
    return this.http.get<WorkspaceResponse>(this.url(`/${skill}`));
  }

  delete(skill: string): Observable<{ deleted: string }> {
    return this.http.delete<{ deleted: string }>(this.url(`/${skill}`));
  }

  listFiles(skill: string): Observable<FileInfo[]> {
    return this.http.get<FileInfo[]>(this.url(`/${skill}/files`));
  }

  downloadFile(skill: string, fileName: string): Observable<Blob> {
    return this.http.get(this.url(`/${skill}/files/${fileName}`), { responseType: 'blob' });
  }

  uploadFile(skill: string, file: File): Observable<unknown> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.http.post(this.url(`/${skill}/files`), form, {
      params: { filename: file.name },
    });
  }

  deleteFile(skill: string, fileName: string): Observable<{ deleted: string }> {
    return this.http.delete<{ deleted: string }>(this.url(`/${skill}/files/${fileName}`));
  }
}
