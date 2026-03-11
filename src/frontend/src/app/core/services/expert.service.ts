import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiConfigService } from './api-config.service';
import { AuthService } from './auth.service';
import { Expert, ExpertCreateRequest } from '../models/expert.models';

@Injectable({ providedIn: 'root' })
export class ExpertService {
  private http   = inject(HttpClient);
  private config = inject(ApiConfigService);
  private auth   = inject(AuthService);

  private get headers(): HttpHeaders {
    const token = this.auth.token();
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  list(): Observable<Expert[]> {
    return this.http.get<Expert[]>(`${this.config.apiUrl}/experts`, { headers: this.headers });
  }

  create(req: ExpertCreateRequest): Observable<Expert> {
    return this.http.post<Expert>(`${this.config.apiUrl}/experts`, req, { headers: this.headers });
  }

  update(id: number, req: Partial<ExpertCreateRequest>): Observable<Expert> {
    return this.http.put<Expert>(`${this.config.apiUrl}/experts/${id}`, req, { headers: this.headers });
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.config.apiUrl}/experts/${id}`, { headers: this.headers });
  }
}
