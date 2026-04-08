import { Component, inject, computed, OnInit, signal, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TaskService } from '../../../core/services/task.service';
import { HumanTask } from '../../../core/models/task.models';
import { MarkdownContentComponent } from '../markdown-content/markdown-content.component';
import { TaskRespondPayload } from '../../../core/models/task.models';

type Tab = 'inbox' | 'sent';

@Component({
  selector: 'app-task-list',
  standalone: true,
  imports: [CommonModule, MarkdownContentComponent],
  template: `
    <div class="flex flex-col h-full">

      <!-- Tab bar -->
      <div class="flex-none flex border-b border-gray-200 dark:border-zinc-800">
        <button
          (click)="activeTab.set('inbox')"
          class="flex-1 py-2 text-xs font-medium transition-colors relative"
          [ngClass]="activeTab() === 'inbox'
            ? 'text-gray-800 dark:text-zinc-100'
            : 'text-gray-400 dark:text-zinc-500 hover:text-gray-600 dark:hover:text-zinc-300'"
        >
          Inbox
          @if (pendingInbox() > 0) {
            <span class="ml-1 inline-flex items-center justify-center w-4 h-4 rounded-full bg-amber-500 text-zinc-900 text-[9px] font-bold">
              {{ pendingInbox() > 9 ? '9+' : pendingInbox() }}
            </span>
          }
          @if (activeTab() === 'inbox') {
            <span class="absolute bottom-0 left-0 right-0 h-0.5 bg-brand rounded-t-full"></span>
          }
        </button>
        <button
          (click)="activeTab.set('sent')"
          class="flex-1 py-2 text-xs font-medium transition-colors relative"
          [ngClass]="activeTab() === 'sent'
            ? 'text-gray-800 dark:text-zinc-100'
            : 'text-gray-400 dark:text-zinc-500 hover:text-gray-600 dark:hover:text-zinc-300'"
        >
          Sent
          @if (pendingSent() > 0) {
            <span class="ml-1 inline-flex items-center justify-center w-4 h-4 rounded-full bg-zinc-300 dark:bg-zinc-600 text-zinc-700 dark:text-zinc-200 text-[9px] font-bold">
              {{ pendingSent() > 9 ? '9+' : pendingSent() }}
            </span>
          }
          @if (activeTab() === 'sent') {
            <span class="absolute bottom-0 left-0 right-0 h-0.5 bg-brand rounded-t-full"></span>
          }
        </button>
      </div>

      <!-- Inbox tab -->
      @if (activeTab() === 'inbox') {
        <div class="flex-1 min-h-0 overflow-y-auto scrollbar-thin flex flex-col">

          @if (inboxPending().length === 0) {
            <div class="flex flex-col items-center justify-center flex-1 gap-2 p-6 text-center">
              <div class="w-9 h-9 rounded-full bg-gray-100 dark:bg-zinc-800 flex items-center justify-center">
                <svg class="w-4 h-4 text-gray-400 dark:text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                </svg>
              </div>
              <p class="text-xs text-gray-400 dark:text-zinc-500">No pending tasks</p>
            </div>
          }

          <!-- Pending approvals -->
          @if (inboxApprovals().length > 0) {
            <section class="p-3 flex flex-col gap-2">
              <div class="flex items-center gap-2 px-1">
                <h3 class="text-xs font-semibold text-gray-500 dark:text-zinc-400 uppercase tracking-wider flex-1">Approvals</h3>
                <span class="text-xs font-semibold bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 rounded-full px-1.5 py-0.5">
                  {{ inboxApprovals().length }}
                </span>
              </div>
              @for (task of inboxApprovals(); track task.id) {
                <div
                  class="flex flex-col gap-1 rounded-xl border border-amber-200 dark:border-amber-800/50 bg-white dark:bg-zinc-900 px-3 py-2.5 cursor-pointer hover:border-amber-400 dark:hover:border-amber-600/60 hover:bg-amber-50/40 dark:hover:bg-amber-950/20 transition-colors"
                  [title]="task.description"
                  (click)="taskSelected.emit(task)"
                >
                  <div class="flex items-start gap-2">
                    <svg class="w-3.5 h-3.5 flex-none mt-0.5 text-amber-500 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <span class="flex-1 text-sm font-medium text-gray-800 dark:text-zinc-100 leading-tight">{{ task.title }}</span>
                    <span class="flex-none text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 whitespace-nowrap">pending</span>
                  </div>
                  <div class="flex items-center gap-1 pl-5 text-xs text-gray-400 dark:text-zinc-500">
                    <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                    </svg>
                    <span>{{ task.assignedBy }}</span>
                    <span class="mx-1">&middot;</span>
                    <span>{{ relativeTime(task.createdAt) }}</span>
                  </div>
                  <div class="flex gap-2 pt-0.5">
                    <button
                      (click)="respondInline(task, { decision: 'approved' }); $event.stopPropagation()"
                      [disabled]="responding() === task.id"
                      class="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 hover:bg-emerald-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      @if (responding() === task.id) {
                        <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/></svg>
                      } @else {
                        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                      }
                      Approve
                    </button>
                    <button
                      (click)="respondInline(task, { decision: 'rejected' }); $event.stopPropagation()"
                      [disabled]="responding() === task.id"
                      class="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold bg-red-500 hover:bg-red-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
                      Reject
                    </button>
                  </div>
                </div>
              }
            </section>
          }

          <!-- Pending reports -->
          @if (inboxReports().length > 0) {
            <section class="p-3 flex flex-col gap-2" [class.border-t]="inboxApprovals().length > 0" [class.border-gray-200]="inboxApprovals().length > 0">
              <div class="flex items-center gap-2 px-1">
                <h3 class="text-xs font-semibold text-gray-500 dark:text-zinc-400 uppercase tracking-wider flex-1">Reports</h3>
                <span class="text-xs font-semibold bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400 rounded-full px-1.5 py-0.5">
                  {{ inboxReports().length }}
                </span>
              </div>
              @for (task of inboxReports(); track task.id) {
                <div
                  class="flex flex-col gap-1 rounded-xl border border-blue-200 dark:border-blue-800/50 bg-white dark:bg-zinc-900 px-3 py-2.5 cursor-pointer hover:border-blue-400 dark:hover:border-blue-600/60 hover:bg-blue-50/30 dark:hover:bg-blue-950/10 transition-colors"
                  [title]="task.description"
                  (click)="taskSelected.emit(task)"
                >
                  <div class="flex items-start gap-2">
                    <svg class="w-3.5 h-3.5 flex-none mt-0.5 text-blue-500 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    <span class="flex-1 text-sm font-medium text-gray-800 dark:text-zinc-100 leading-tight">{{ task.title }}</span>
                    <span class="flex-none text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 whitespace-nowrap">pending</span>
                  </div>
                  <div class="flex items-center gap-1 pl-5 text-xs text-gray-400 dark:text-zinc-500">
                    <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                    </svg>
                    <span>{{ task.assignedBy }}</span>
                    <span class="mx-1">&middot;</span>
                    <span>{{ relativeTime(task.createdAt) }}</span>
                  </div>
                  <div class="flex gap-2 pt-0.5">
                    <button
                      (click)="respondInline(task, { acknowledged: true }); $event.stopPropagation()"
                      [disabled]="responding() === task.id"
                      class="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold bg-blue-500 hover:bg-blue-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      @if (responding() === task.id) {
                        <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/></svg>
                      } @else {
                        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                      }
                      Acknowledge
                    </button>
                  </div>
                </div>
              }
            </section>
          }

          <!-- Pending form inputs -->
          @if (inboxFormInputs().length > 0) {
            <section class="p-3 flex flex-col gap-2" [class.border-t]="inboxApprovals().length > 0 || inboxReports().length > 0" [class.border-gray-200]="inboxApprovals().length > 0 || inboxReports().length > 0">
              <div class="flex items-center gap-2 px-1">
                <h3 class="text-xs font-semibold text-gray-500 dark:text-zinc-400 uppercase tracking-wider flex-1">Forms</h3>
                <span class="text-xs font-semibold bg-teal-100 dark:bg-teal-900/40 text-teal-700 dark:text-teal-400 rounded-full px-1.5 py-0.5">
                  {{ inboxFormInputs().length }}
                </span>
              </div>
              @for (task of inboxFormInputs(); track task.id) {
                <div
                  class="flex flex-col gap-1 rounded-xl border border-teal-200 dark:border-teal-800/50 bg-white dark:bg-zinc-900 px-3 py-2.5 cursor-pointer hover:border-teal-400 dark:hover:border-teal-600/60 hover:bg-teal-50/30 dark:hover:bg-teal-950/10 transition-colors"
                  [title]="task.description"
                  (click)="taskSelected.emit(task)"
                >
                  <div class="flex items-start gap-2">
                    <svg class="w-3.5 h-3.5 flex-none mt-0.5 text-teal-500 dark:text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>
                    </svg>
                    <span class="flex-1 text-sm font-medium text-gray-800 dark:text-zinc-100 leading-tight">{{ task.title }}</span>
                    <span class="flex-none text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-400 whitespace-nowrap">pending</span>
                  </div>
                  <div class="flex items-center gap-1 pl-5 text-xs text-gray-400 dark:text-zinc-500">
                    <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                    </svg>
                    <span>{{ task.assignedBy }}</span>
                    <span class="mx-1">&middot;</span>
                    <span>{{ relativeTime(task.createdAt) }}</span>
                  </div>
                  <div class="flex gap-2 pt-0.5" (click)="$event.stopPropagation()">
                    <button
                      (click)="taskSelected.emit(task)"
                      class="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold bg-teal-500 hover:bg-teal-600 text-white transition-colors"
                    >
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
                      Fill out form
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
                    </button>
                  </div>
                </div>
              }
            </section>
          }

          <!-- Pending file requests -->
          @if (inboxFileRequests().length > 0) {
            <section class="p-3 flex flex-col gap-2" [class.border-t]="inboxApprovals().length > 0 || inboxReports().length > 0" [class.border-gray-200]="inboxApprovals().length > 0 || inboxReports().length > 0">
              <div class="flex items-center gap-2 px-1">
                <h3 class="text-xs font-semibold text-gray-500 dark:text-zinc-400 uppercase tracking-wider flex-1">File Requests</h3>
                <span class="text-xs font-semibold bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-400 rounded-full px-1.5 py-0.5">
                  {{ inboxFileRequests().length }}
                </span>
              </div>
              @for (task of inboxFileRequests(); track task.id) {
                <div
                  class="flex flex-col gap-1 rounded-xl border border-violet-200 dark:border-violet-800/50 bg-white dark:bg-zinc-900 px-3 py-2.5 cursor-pointer hover:border-violet-400 dark:hover:border-violet-600/60 hover:bg-violet-50/30 dark:hover:bg-violet-950/10 transition-colors"
                  [title]="task.description"
                  (click)="taskSelected.emit(task)"
                >
                  <div class="flex items-start gap-2">
                    <svg class="w-3.5 h-3.5 flex-none mt-0.5 text-violet-500 dark:text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
                    </svg>
                    <span class="flex-1 text-sm font-medium text-gray-800 dark:text-zinc-100 leading-tight">{{ task.title }}</span>
                    <span class="flex-none text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400 whitespace-nowrap">pending</span>
                  </div>
                  <div class="flex items-center gap-1 pl-5 text-xs text-gray-400 dark:text-zinc-500">
                    <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                    </svg>
                    <span>{{ task.assignedBy }}</span>
                    <span class="mx-1">&middot;</span>
                    <span>{{ relativeTime(task.createdAt) }}</span>
                  </div>
                  <div class="flex gap-2 pt-0.5" (click)="$event.stopPropagation()">
                    <button
                      (click)="taskSelected.emit(task)"
                      class="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold bg-violet-500 hover:bg-violet-600 text-white transition-colors"
                    >
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>
                      Upload files
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
                    </button>
                  </div>
                </div>
              }
            </section>
          }

          <!-- Completed received -->
          @if (inboxCompleted().length > 0) {
            <section class="p-3 border-t border-gray-200 dark:border-zinc-800">
              <button
                (click)="showInboxCompleted = !showInboxCompleted"
                class="flex items-center gap-2 w-full text-left px-1 py-0.5"
              >
                <h3 class="text-xs font-semibold text-gray-400 dark:text-zinc-500 uppercase tracking-wider flex-1">Completed</h3>
                <svg class="w-3.5 h-3.5 text-gray-400 transition-transform" [class.rotate-180]="showInboxCompleted" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
                </svg>
              </button>
              @if (showInboxCompleted) {
                <div class="mt-2 flex flex-col gap-1.5">
                  @for (task of inboxCompleted(); track task.id) {
                    <ng-container *ngTemplateOutlet="completedRow; context: { $implicit: task }" />
                  }
                </div>
              }
            </section>
          }

        </div>
      }

      <!-- Sent tab -->
      @if (activeTab() === 'sent') {
        <div class="flex-1 min-h-0 overflow-y-auto scrollbar-thin flex flex-col">

          @if (taskSvc.originatedTasks().length === 0) {
            <div class="flex flex-col items-center justify-center flex-1 gap-2 p-6 text-center">
              <div class="w-9 h-9 rounded-full bg-gray-100 dark:bg-zinc-800 flex items-center justify-center">
                <svg class="w-4 h-4 text-gray-400 dark:text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                </svg>
              </div>
              <p class="text-xs text-gray-400 dark:text-zinc-500">No sent tasks</p>
            </div>
          }

          @if (sentPending().length > 0) {
            <section class="p-3 flex flex-col gap-1.5">
              <div class="flex items-center gap-2 px-1">
                <h3 class="text-xs font-semibold text-gray-500 dark:text-zinc-400 uppercase tracking-wider flex-1">Awaiting response</h3>
                <span class="text-xs font-semibold bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 rounded-full px-1.5 py-0.5">
                  {{ sentPending().length }}
                </span>
              </div>
              @for (task of sentPending(); track task.id) {
                <div class="flex flex-col gap-1 rounded-xl border bg-white dark:bg-zinc-900 px-3 py-2.5 transition-colors"
                  [ngClass]="confirmingRevoke() === task.id
                    ? 'border-red-300 dark:border-red-700/60'
                    : 'border-gray-200 dark:border-zinc-700/60'"
                  [title]="task.description"
                >
                  <div class="flex items-start gap-2">
                    <ng-container *ngTemplateOutlet="taskTypeIcon; context: { $implicit: task }" />
                    <span class="flex-1 text-sm font-medium text-gray-800 dark:text-zinc-100 leading-tight">{{ task.title }}</span>
                    @if (confirmingRevoke() !== task.id) {
                      <span class="flex-none text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 whitespace-nowrap">pending</span>
                    }
                  </div>
                  @if (confirmingRevoke() === task.id) {
                    <div class="flex items-center gap-2 pt-1 pl-5">
                      <span class="flex-1 text-xs text-red-600 dark:text-red-400">Revoke this task?</span>
                      <button
                        (click)="revokeTask(task)"
                        [disabled]="revoking() === task.id"
                        class="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-red-500 hover:bg-red-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                      >
                        @if (revoking() === task.id) {
                          <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"/>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                          </svg>
                        }
                        Revoke
                      </button>
                      <button
                        (click)="confirmingRevoke.set(null)"
                        [disabled]="revoking() === task.id"
                        class="text-[11px] font-medium px-2 py-0.5 rounded-md bg-gray-100 dark:bg-zinc-700 hover:bg-gray-200 dark:hover:bg-zinc-600 text-gray-600 dark:text-zinc-300 transition-colors disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    </div>
                  }
                  @if (confirmingRevoke() !== task.id) {
                    <div class="flex items-center gap-1 pl-5 text-xs text-gray-400 dark:text-zinc-500">
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                      </svg>
                      <span>{{ task.assignedTo }}</span>
                      <span class="mx-1">&middot;</span>
                      <span>{{ relativeTime(task.createdAt) }}</span>
                    </div>
                    <button
                      (click)="confirmingRevoke.set(task.id)"
                      class="w-full flex items-center justify-center gap-1.5 py-1.5 mt-0.5 rounded-lg text-xs font-semibold text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800/50 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    >
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                      </svg>
                      Revoke
                    </button>
                  }
                </div>
              }
            </section>
          }

          @if (sentCompleted().length > 0) {
            <section class="p-3 flex flex-col gap-1.5" [class.border-t]="sentPending().length > 0" [class.border-gray-200]="sentPending().length > 0" [class.dark:border-zinc-800]="sentPending().length > 0">
              <div class="flex items-center gap-2 px-1">
                <h3 class="text-xs font-semibold text-gray-500 dark:text-zinc-400 uppercase tracking-wider flex-1">Responded</h3>
              </div>
              @for (task of sentCompleted(); track task.id) {
                <div class="flex flex-col rounded-xl border bg-white dark:bg-zinc-900 overflow-hidden transition-colors"
                  [ngClass]="confirmingDelete() === task.id
                    ? 'border-red-300 dark:border-red-700/60'
                    : 'border-gray-200 dark:border-zinc-700/60 cursor-pointer hover:bg-gray-50 dark:hover:bg-zinc-800/60'"
                  [title]="task.title + (task.description ? '\n\n' + task.description : '')"
                  (click)="confirmingDelete() !== task.id && toggleExpanded(task.id)"
                >
                  <!-- Summary row -->
                  <div class="flex items-center gap-1.5 px-3 py-2.5">
                    @if (confirmingDelete() !== task.id) {
                      <svg class="w-2.5 h-2.5 flex-none text-gray-400 dark:text-zinc-500 transition-transform duration-150"
                        [class.rotate-90]="expandedCompleted() === task.id"
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
                      </svg>
                    }
                    <ng-container *ngTemplateOutlet="taskTypeIcon; context: { $implicit: task }" />
                    <span class="flex-1 text-sm font-medium text-gray-700 dark:text-zinc-200 leading-tight">{{ task.title }}</span>
                    @if (confirmingDelete() !== task.id) {
                      <ng-container *ngTemplateOutlet="statusBadge; context: { $implicit: task }" />
                      <button
                        (click)="confirmingDelete.set(task.id); $event.stopPropagation()"
                        title="Delete"
                        class="flex-none w-5 h-5 flex items-center justify-center rounded-md text-gray-300 dark:text-zinc-600 hover:text-red-400 dark:hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                      >
                        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                      </button>
                    }
                  </div>
                  <!-- Delete confirmation -->
                  @if (confirmingDelete() === task.id) {
                    <div class="flex items-center gap-2 px-3 pb-2.5" (click)="$event.stopPropagation()">
                      <span class="flex-1 text-xs text-red-600 dark:text-red-400">Delete this task?</span>
                      <button
                        (click)="deleteTask(task, $event)"
                        [disabled]="deleting() === task.id"
                        class="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-red-500 hover:bg-red-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                      >
                        @if (deleting() === task.id) {
                          <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"/>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                          </svg>
                        }
                        Delete
                      </button>
                      <button
                        (click)="confirmingDelete.set(null); $event.stopPropagation()"
                        [disabled]="deleting() === task.id"
                        class="text-[11px] font-medium px-2 py-0.5 rounded-md bg-gray-100 dark:bg-zinc-700 hover:bg-gray-200 dark:hover:bg-zinc-600 text-gray-600 dark:text-zinc-300 transition-colors disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    </div>
                  } @else {
                    <!-- Meta row -->
                    <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 px-3 pb-2 pl-7 text-[10px] text-gray-400 dark:text-zinc-500">
                      <span>to <span class="font-medium">{{ task.assignedTo }}</span></span>
                      <span class="opacity-50">&middot;</span>
                      <span>sent {{ relativeTime(task.createdAt) }}</span>
                      @if (task.respondedAt) {
                        <span class="opacity-50">&middot;</span>
                        <span>responded {{ relativeTime(task.respondedAt) }}</span>
                      }
                    </div>
                    <!-- Expanded response -->
                    @if (expandedCompleted() === task.id) {
                      <div class="mx-3 mb-2.5">
                        <div class="flex items-start gap-2">
                          <div class="mt-0.5 shrink-0 w-4 h-4 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center">
                            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="text-amber-600 dark:text-amber-400">
                              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
                            </svg>
                          </div>
                          <div class="flex-1 rounded-xl rounded-tl-sm border border-amber-300/60 dark:border-amber-700/50 bg-amber-50/60 dark:bg-amber-950/20 px-3 py-2">
                            <p class="text-[10px] font-medium text-amber-700 dark:text-amber-400 mb-1">Task response</p>
                            <app-markdown-content
                              [text]="formatTaskResponse(task)"
                              [finalized]="true"
                              [intermediary]="false">
                            </app-markdown-content>
                          </div>
                        </div>
                      </div>
                    }
                  }
                </div>
              }
            </section>
          }

        </div>
      }

    </div>

    <!-- Shared templates -->
    <ng-template #completedRow let-task>
      <div
        class="flex flex-col rounded-lg bg-gray-50 dark:bg-zinc-800/50 overflow-hidden cursor-pointer hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors"
        [title]="task.title + (task.description ? '\n\n' + task.description : '')"
        (click)="toggleExpanded(task.id)"
      >
        <!-- Summary row -->
        <div class="flex items-center gap-1.5 px-2 py-1.5">
          <svg class="w-2.5 h-2.5 flex-none text-gray-400 dark:text-zinc-500 transition-transform duration-150"
            [class.rotate-90]="expandedCompleted() === task.id"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
          </svg>
          <span class="flex-1 text-xs text-gray-500 dark:text-zinc-400 truncate">{{ task.title }}</span>
          @if (confirmingDelete() !== task.id) {
            <ng-container *ngTemplateOutlet="statusBadge; context: { $implicit: task }" />
            <button
              (click)="confirmingDelete.set(task.id); $event.stopPropagation()"
              title="Delete"
              class="flex-none w-4 h-4 flex items-center justify-center rounded text-gray-300 dark:text-zinc-600 hover:text-red-400 dark:hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              <svg class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
            </button>
          }
        </div>
        <!-- Delete confirmation -->
        @if (confirmingDelete() === task.id) {
          <div class="flex items-center gap-2 px-2 pb-1.5 pl-6" (click)="$event.stopPropagation()">
            <span class="flex-1 text-[10px] text-red-500 dark:text-red-400">Delete this task?</span>
            <button
              (click)="deleteTask(task, $event)"
              [disabled]="deleting() === task.id"
              class="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-red-500 hover:bg-red-600 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
            >
              @if (deleting() === task.id) {
                <svg class="w-2.5 h-2.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"/>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
              }
              Delete
            </button>
            <button
              (click)="confirmingDelete.set(null); $event.stopPropagation()"
              [disabled]="deleting() === task.id"
              class="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-200 dark:bg-zinc-700 hover:bg-gray-300 dark:hover:bg-zinc-600 text-gray-600 dark:text-zinc-300 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        }
        @if (confirmingDelete() !== task.id) {
          <!-- Meta row -->
          <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 px-2 pb-1.5 pl-6 text-[10px] text-gray-400 dark:text-zinc-500">
            <span>from <span class="font-medium">{{ task.assignedBy }}</span></span>
            <span class="opacity-50">&middot;</span>
            <span>sent {{ relativeTime(task.createdAt) }}</span>
            @if (task.respondedAt) {
              <span class="opacity-50">&middot;</span>
              <span>responded {{ relativeTime(task.respondedAt) }}</span>
            }
          </div>
        }
        <!-- Expanded response -->
        @if (expandedCompleted() === task.id && confirmingDelete() !== task.id) {
          <div class="mx-2 mb-2 mt-0.5">
            <div class="flex items-start gap-2">
              <div class="mt-0.5 shrink-0 w-4 h-4 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center">
                <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="text-amber-600 dark:text-amber-400">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
                </svg>
              </div>
              <div class="flex-1 rounded-xl rounded-tl-sm border border-amber-300/60 dark:border-amber-700/50 bg-amber-50/60 dark:bg-amber-950/20 px-3 py-2">
                <p class="text-[10px] font-medium text-amber-700 dark:text-amber-400 mb-1">Task response</p>
                <app-markdown-content
                  [text]="formatTaskResponse(task)"
                  [finalized]="true"
                  [intermediary]="false">
                </app-markdown-content>
              </div>
            </div>
          </div>
        }
      </div>
    </ng-template>

    <ng-template #statusBadge let-task>
      @if (task.status === 'cancelled') {
        <span class="flex-none text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-zinc-800 text-gray-500 dark:text-zinc-400 whitespace-nowrap">cancelled</span>
      } @else if (task.taskType === 'approval') {
        <span class="flex-none text-[10px] font-semibold px-1.5 py-0.5 rounded-full whitespace-nowrap"
          [ngClass]="task.response?.decision === 'approved'
            ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400'
            : task.response?.decision === 'rejected'
              ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400'
              : 'bg-gray-100 dark:bg-zinc-800 text-gray-500 dark:text-zinc-400'"
        >{{ task.response?.decision ?? task.status }}</span>
      } @else if (task.taskType === 'file_request') {
        <span class="flex-none text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 whitespace-nowrap">uploaded</span>
      } @else if (task.taskType === 'form_input') {
        <span class="flex-none text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 whitespace-nowrap">submitted</span>
      } @else {
        <span class="flex-none text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 whitespace-nowrap">ack'd</span>
      }
    </ng-template>

    <ng-template #taskTypeIcon let-task>
      @if (task.taskType === 'approval') {
        <svg class="w-3.5 h-3.5 flex-none mt-0.5 text-amber-500 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      } @else if (task.taskType === 'file_request') {
        <svg class="w-3.5 h-3.5 flex-none mt-0.5 text-violet-500 dark:text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
        </svg>
      } @else if (task.taskType === 'form_input') {
        <svg class="w-3.5 h-3.5 flex-none mt-0.5 text-teal-500 dark:text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>
        </svg>
      } @else {
        <svg class="w-3.5 h-3.5 flex-none mt-0.5 text-blue-500 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
      }
    </ng-template>
  `,
})
export class TaskListComponent implements OnInit {
  readonly taskSvc = inject(TaskService);

  @Output() taskSelected = new EventEmitter<HumanTask>();
  @Output() taskRevoked  = new EventEmitter<void>();

  activeTab = signal<Tab>('inbox');
  showInboxCompleted = false;

  // ── Inbox (assigned to me) ─────────────────────────────────────────────────
  inboxPending      = computed(() => this.taskSvc.assignedTasks().filter(t => t.status === 'pending'));
  inboxApprovals    = computed(() => this.inboxPending().filter(t => t.taskType === 'approval'));
  inboxReports      = computed(() => this.inboxPending().filter(t => t.taskType === 'report'));
  inboxFormInputs   = computed(() => this.inboxPending().filter(t => t.taskType === 'form_input'));
  inboxFileRequests = computed(() => this.inboxPending().filter(t => t.taskType === 'file_request'));
  inboxCompleted = computed(() =>
    this.taskSvc.assignedTasks().filter(t => t.status !== 'pending').slice(0, 10)
  );
  pendingInbox = computed(() => this.inboxPending().length);

  // ── Sent (originated by me) ────────────────────────────────────────────────
  sentPending   = computed(() => this.taskSvc.originatedTasks().filter(t => t.status === 'pending'));
  sentCompleted = computed(() => this.taskSvc.originatedTasks().filter(t => t.status !== 'pending'));
  pendingSent   = computed(() => this.sentPending().length);

  responding = signal<string | null>(null);
  revoking = signal<string | null>(null);
  confirmingRevoke = signal<string | null>(null);
  expandedCompleted = signal<string | null>(null);
  confirmingDelete = signal<string | null>(null);
  deleting = signal<string | null>(null);

  respondInline(task: HumanTask, payload: TaskRespondPayload): void {
    if (this.responding()) return;
    this.responding.set(task.id);
    this.taskSvc.respond(task.id, payload).subscribe({
      next: () => { this.responding.set(null); this.taskSvc.refresh(); },
      error: () => { this.responding.set(null); },
    });
  }

  toggleExpanded(id: string): void {
    this.expandedCompleted.update(cur => cur === id ? null : id);
  }

  formatTaskResponse(task: HumanTask): string {
    const r = task.response;
    if (!r) {
      return task.status === 'cancelled' ? 'Task was cancelled by the originator.' : 'No response recorded.';
    }
    if (r.cancelled) {
      return 'Task was cancelled by the originator.';
    }
    let text = '';
    if (task.taskType === 'approval') {
      const dec = r.decision ?? 'unknown';
      text = `**Approval decision: ${dec.charAt(0).toUpperCase() + dec.slice(1)}**`;
    } else if (task.taskType === 'file_request') {
      const files = r.files ?? [];
      text = `**Files uploaded: ${files.length} file(s)**`;
      if (files.length) {
        text += '\n\n' + files.map(f => `- \`${f}\``).join('\n');
      }
    } else if (task.taskType === 'form_input') {
      const data = r.form_data ?? {};
      const entries = Object.entries(data).filter(([k]) => k !== 'submit');
      text = '**Form submitted.**';
      if (entries.length) {
        text += '\n\n' + entries.map(([k, v]) => {
          const val = Array.isArray(v) ? v.join(', ') : String(v);
          return `- **${k}**: ${val}`;
        }).join('\n');
      }
    } else {
      text = '**Report acknowledged.**';
    }
    if (r.feedback) text += `\n\nFeedback: ${r.feedback}`;
    return text;
  }

  deleteTask(task: HumanTask, event: Event): void {
    event.stopPropagation();
    if (this.deleting()) return;
    this.deleting.set(task.id);
    this.taskSvc.cancel(task.id).subscribe({
      next: () => {
        this.deleting.set(null);
        this.confirmingDelete.set(null);
        if (this.expandedCompleted() === task.id) this.expandedCompleted.set(null);
        this.taskSvc.refresh();
      },
      error: () => {
        this.deleting.set(null);
        this.confirmingDelete.set(null);
      },
    });
  }

  revokeTask(task: HumanTask): void {
    if (this.revoking()) return;
    this.revoking.set(task.id);
    this.taskSvc.cancel(task.id).subscribe({
      next: () => {
        this.revoking.set(null);
        this.confirmingRevoke.set(null);
        this.taskSvc.refresh();
        this.taskRevoked.emit();
      },
      error: () => {
        this.revoking.set(null);
        this.confirmingRevoke.set(null);
      },
    });
  }

  ngOnInit(): void {
    this.taskSvc.refresh();
  }

  relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 60_000)    return 'just now';
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    return `${Math.floor(diff / 86_400_000)}d ago`;
  }
}
