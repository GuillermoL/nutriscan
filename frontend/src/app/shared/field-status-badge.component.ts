import { Component, computed, input } from '@angular/core';

import { FieldStatus } from '../core/models/extraction.model';

@Component({
  selector: 'app-field-status-badge',
  standalone: true,
  templateUrl: './field-status-badge.component.html',
  styleUrl: './field-status-badge.component.css'
})
export class FieldStatusBadgeComponent {
  readonly status = input.required<FieldStatus>();
  readonly reason = input<string | null>(null);
  readonly rawText = input<string | null>(null);

  readonly tooltip = computed(() => {
    const parts: string[] = [];
    if (this.reason()) {
      parts.push(`Motivo: ${this.reason()}`);
    }
    if (this.rawText()) {
      parts.push(`Texto leído: "${this.rawText()}"`);
    }
    return parts.join('\n');
  });
}
