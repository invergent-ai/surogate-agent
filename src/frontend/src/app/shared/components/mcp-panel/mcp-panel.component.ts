import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { McpService } from '../../../core/services/mcp.service';
import { McpServer } from '../../../core/models/mcp.models';

@Component({
  selector: 'app-mcp-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './mcp-panel.component.html',
})
export class McpPanelComponent implements OnInit {
  private mcpService = inject(McpService);

  servers = signal<McpServer[]>([]);
  loading = signal(false);
  error = signal('');
  confirmRemove = signal<string | null>(null);
  removing = signal<string | null>(null);
  // Track servers with in-flight start/stop
  actionPending = signal<Set<string>>(new Set());
  // Track servers with expanded tools list
  expandedTools = signal<Set<string>>(new Set());

  // Add HTTP server form
  showAddForm = signal(false);
  addName = signal('');
  addUrl = signal('');
  adding = signal(false);
  addError = signal('');

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.mcpService.list().subscribe({
      next: (list) => {
        this.servers.set(list);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Failed to load MCP servers.');
        this.loading.set(false);
      },
    });
  }

  isPending(name: string): boolean {
    return this.actionPending().has(name);
  }

  isExpanded(name: string): boolean {
    return this.expandedTools().has(name);
  }

  toggleTools(name: string): void {
    const s = new Set(this.expandedTools());
    s.has(name) ? s.delete(name) : s.add(name);
    this.expandedTools.set(s);
  }

  extraCount(server: McpServer): number {
    return Math.max(0, (server.tools?.length ?? 0) - 3);
  }

  startServer(name: string): void {
    const s = new Set(this.actionPending());
    s.add(name);
    this.actionPending.set(s);
    this.mcpService.start(name).subscribe({
      next: (updated) => {
        this.servers.set(this.servers().map(sv => sv.name === name ? updated : sv));
        const ns = new Set(this.actionPending());
        ns.delete(name);
        this.actionPending.set(ns);
      },
      error: () => {
        const ns = new Set(this.actionPending());
        ns.delete(name);
        this.actionPending.set(ns);
        this.error.set(`Failed to start '${name}'.`);
      },
    });
  }

  stopServer(name: string): void {
    const s = new Set(this.actionPending());
    s.add(name);
    this.actionPending.set(s);
    this.mcpService.stop(name).subscribe({
      next: (updated) => {
        this.servers.set(this.servers().map(sv => sv.name === name ? updated : sv));
        const ns = new Set(this.actionPending());
        ns.delete(name);
        this.actionPending.set(ns);
      },
      error: () => {
        const ns = new Set(this.actionPending());
        ns.delete(name);
        this.actionPending.set(ns);
        this.error.set(`Failed to stop '${name}'.`);
      },
    });
  }

  askRemove(name: string): void {
    this.confirmRemove.set(name);
  }

  cancelRemove(): void {
    this.confirmRemove.set(null);
  }

  doRemove(name: string): void {
    this.confirmRemove.set(null);
    this.removing.set(name);
    this.mcpService.remove(name).subscribe({
      next: () => {
        this.removing.set(null);
        this.load();
      },
      error: () => {
        this.removing.set(null);
        this.error.set(`Failed to remove '${name}'.`);
      },
    });
  }

  openAddForm(): void {
    this.showAddForm.set(true);
    this.addName.set('');
    this.addUrl.set('');
    this.addError.set('');
  }

  cancelAdd(): void {
    this.showAddForm.set(false);
    this.addError.set('');
  }

  addServer(): void {
    const name = this.addName().trim();
    const url = this.addUrl().trim();
    if (!name) { this.addError.set('Name is required.'); return; }
    if (!url) { this.addError.set('URL is required.'); return; }
    try { new URL(url); } catch { this.addError.set('Invalid URL.'); return; }
    this.adding.set(true);
    this.addError.set('');
    this.mcpService.register(name, url).subscribe({
      next: (server) => {
        this.adding.set(false);
        this.showAddForm.set(false);
        this.servers.set([...this.servers(), server]);
      },
      error: (err) => {
        this.adding.set(false);
        const detail = err?.error?.detail ?? 'Failed to register server.';
        this.addError.set(detail);
      },
    });
  }
}
