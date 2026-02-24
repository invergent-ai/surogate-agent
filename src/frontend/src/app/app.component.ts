import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ThemeService } from './core/services/theme.service';
import { ToastComponent } from './shared/components/toast/toast.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, ToastComponent],
  template: '<router-outlet /><app-toast />',
})
export class AppComponent {
  // Inject ThemeService here so it initialises immediately and applies
  // the saved theme class to <html> before any page renders.
  private _theme = inject(ThemeService);
}
