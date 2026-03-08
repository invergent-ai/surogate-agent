import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiConfigService } from './api-config.service';
import { McpServer } from '../models/mcp.models';


@Injectable({ providedIn: 'root' })
export class McpService {
  constructor(private http: HttpClient, private config: ApiConfigService) {}

  private url(path = ''): string {
    return `${this.config.apiUrl}/mcp-servers${path}`;
  }

  list(): Observable<McpServer[]> {
    return this.http.get<McpServer[]>(this.url());
  }

  get(name: string): Observable<McpServer> {
    return this.http.get<McpServer>(this.url(`/${name}`));
  }

  remove(name: string): Observable<void> {
    return this.http.delete<void>(this.url(`/${name}`));
  }

  start(name: string): Observable<McpServer> {
    return this.http.post<McpServer>(this.url(`/${name}/start`), {});
  }

  stop(name: string): Observable<McpServer> {
    return this.http.post<McpServer>(this.url(`/${name}/stop`), {});
  }

  register(name: string, serverUrl: string): Observable<McpServer> {
    const parsed = new URL(serverUrl);
    const host = parsed.hostname;
    const port = parseInt(parsed.port) || (parsed.protocol === 'https:' ? 443 : 80);
    // Backend auto-detects transport (sse vs streamable_http) by probing repo_url.
    return this.http.post<McpServer>(this.url(), {
      name,
      host,
      port,
      repo_url: serverUrl,
    });
  }

  exportServer(name: string): Observable<Blob> {
    return this.http.get(this.url(`/${name}/export`), { responseType: 'blob' });
  }

  importServer(file: File): Observable<McpServer> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<McpServer>(this.url('/import'), form);
  }
}
