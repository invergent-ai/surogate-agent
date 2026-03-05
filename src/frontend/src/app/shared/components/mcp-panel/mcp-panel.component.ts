import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { McpService } from '../../../core/services/mcp.service';
import { McpServer } from '../../../core/models/mcp.models';

@Component({
  selector: 'app-mcp-panel',
  standalone: true,
  imports: [CommonModule],
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

  toolNames(server: McpServer, expanded: boolean): string {
    if (!server.tools || server.tools.length === 0) return 'No tools';
    if (expanded) return server.tools.map(t => t.name).join(', ');
    return server.tools.slice(0, 3).map(t => t.name).join(', ');
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
}
