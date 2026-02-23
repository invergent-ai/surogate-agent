import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiConfigService } from './api-config.service';
import {
  FileInfo,
  SkillCreateRequest,
  SkillListItem,
  SkillResponse,
  ValidationResult,
} from '../models/skill.models';

@Injectable({ providedIn: 'root' })
export class SkillsService {
  constructor(private http: HttpClient, private config: ApiConfigService) {}

  private url(path = ''): string {
    return `${this.config.apiUrl}/skills${path}`;
  }

  list(role: 'all' | 'developer' | 'user' = 'all'): Observable<SkillListItem[]> {
    return this.http.get<SkillListItem[]>(this.url(), { params: { role } });
  }

  get(name: string): Observable<SkillResponse> {
    return this.http.get<SkillResponse>(this.url(`/${name}`));
  }

  create(req: SkillCreateRequest): Observable<SkillResponse> {
    return this.http.post<SkillResponse>(this.url(), req);
  }

  delete(name: string): Observable<{ deleted: string }> {
    return this.http.delete<{ deleted: string }>(this.url(`/${name}`));
  }

  validate(name: string): Observable<ValidationResult> {
    return this.http.post<ValidationResult>(this.url(`/${name}/validate`), {});
  }

  listFiles(name: string): Observable<FileInfo[]> {
    return this.http.get<FileInfo[]>(this.url(`/${name}/files`));
  }

  downloadFile(skillName: string, fileName: string): Observable<Blob> {
    return this.http.get(this.url(`/${skillName}/files/${fileName}`), { responseType: 'blob' });
  }

  uploadFile(skillName: string, file: File, force = false): Observable<unknown> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post(
      this.url(`/${skillName}/files/${file.name}`) + (force ? '?force=true' : ''),
      form
    );
  }

  deleteFile(skillName: string, fileName: string): Observable<{ deleted: string }> {
    return this.http.delete<{ deleted: string }>(this.url(`/${skillName}/files/${fileName}`));
  }
}
