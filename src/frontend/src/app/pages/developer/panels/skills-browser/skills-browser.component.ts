import {
  Component, Output, EventEmitter, signal, OnInit
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SkillsService } from '../../../../core/services/skills.service';
import {
  FileInfo, SkillListItem, SkillResponse, ValidationResult
} from '../../../../core/models/skill.models';
import { ValidationBadgeComponent } from '../../../../shared/components/validation-badge/validation-badge.component';
import { FileListComponent } from '../../../../shared/components/file-list/file-list.component';
import { FileViewerComponent } from '../../../../shared/components/file-viewer/file-viewer.component';

@Component({
  selector: 'app-skills-browser',
  standalone: true,
  imports: [CommonModule, FormsModule, ValidationBadgeComponent, FileListComponent, FileViewerComponent],
  templateUrl: './skills-browser.component.html',
})
export class SkillsBrowserComponent implements OnInit {
  @Output() skillSelected = new EventEmitter<string>();

  skills = signal<SkillListItem[]>([]);
  filter = signal('');
  selectedSkill = signal<SkillResponse | null>(null);
  helperFiles = signal<FileInfo[]>([]);
  validation = signal<ValidationResult | null>(null);
  validating = signal(false);
  loading = signal(false);
  saving = signal(false);

  filteredSkills = () => {
    const q = this.filter().toLowerCase();
    return this.skills().filter(s =>
      !q || s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)
    );
  };

  constructor(private skillsService: SkillsService) {}

  ngOnInit() { this.loadSkills(); }

  loadSkills() {
    this.skillsService.list('developer').subscribe(list => this.skills.set(list));
  }

  selectSkill(name: string) {
    this.skillSelected.emit(name);
    this.loading.set(true);
    this.validation.set(null);
    this.skillsService.get(name).subscribe(sk => {
      this.selectedSkill.set(sk);
      this.helperFiles.set(sk.helper_files);
      this.loading.set(false);
    });
  }

  validate() {
    const sk = this.selectedSkill();
    if (!sk) return;
    this.validating.set(true);
    this.skillsService.validate(sk.name).subscribe(r => {
      this.validation.set(r);
      this.validating.set(false);
    });
  }

  saveSkillMd(content: string) {
    const sk = this.selectedSkill();
    if (!sk) return;
    this.saving.set(true);
    // Re-upload SKILL.md as a file to update it
    const blob = new Blob([content], { type: 'text/markdown' });
    const file = new File([blob], 'SKILL.md', { type: 'text/markdown' });
    this.skillsService.uploadFile(sk.name, file, true).subscribe({
      next: () => {
        this.saving.set(false);
        this.selectSkill(sk.name);
      },
      error: () => this.saving.set(false),
    });
  }

  refreshFiles() {
    const sk = this.selectedSkill();
    if (!sk) return;
    this.skillsService.listFiles(sk.name).subscribe(files => this.helperFiles.set(files));
  }

  deleteSkill(name: string) {
    if (!confirm(`Delete skill '${name}'? This cannot be undone.`)) return;
    this.skillsService.delete(name).subscribe(() => {
      if (this.selectedSkill()?.name === name) this.selectedSkill.set(null);
      this.loadSkills();
    });
  }

  downloadFile = (name: string) => {
    const sk = this.selectedSkill()!;
    return this.skillsService.downloadFile(sk.name, name);
  };

  uploadFile = (file: File) => {
    const sk = this.selectedSkill()!;
    return this.skillsService.uploadFile(sk.name, file);
  };

  deleteFile = (name: string) => {
    const sk = this.selectedSkill()!;
    return this.skillsService.deleteFile(sk.name, name);
  };
}
