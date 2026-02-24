import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ThemeService } from './core/services/theme.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class AppComponent {
  // Inject ThemeService here so it initialises immediately and applies
  // the saved theme class to <html> before any page renders.
  private _theme = inject(ThemeService);
}
