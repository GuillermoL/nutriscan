import { Component, computed, input } from '@angular/core';

import {
  FIELD_LABELS,
  FieldName,
  LabelExtractionResponse,
  NUTRITION_FIELD_NAMES,
  TrafficLightRule
} from '../../core/models/extraction.model';
import { FieldStatusBadgeComponent } from '../../shared/field-status-badge.component';
import { MacroDonutComponent } from './macro-donut.component';
import { TrafficLightBarComponent } from './traffic-light-bar.component';

@Component({
  selector: 'app-result-card',
  standalone: true,
  imports: [MacroDonutComponent, TrafficLightBarComponent, FieldStatusBadgeComponent],
  templateUrl: './result-card.component.html',
  styleUrl: './result-card.component.css'
})
export class ResultCardComponent {
  readonly result = input.required<LabelExtractionResponse>();
  readonly trafficLightRules = input<Record<FieldName, TrafficLightRule> | null>(null);

  readonly fieldNames = NUTRITION_FIELD_NAMES;
  readonly fieldLabels = FIELD_LABELS;

  readonly foundCount = computed(
    () => this.fieldNames.filter((name) => this.result().fields[name].status !== 'not_found').length
  );

  ruleFor(name: FieldName): TrafficLightRule | null {
    return this.trafficLightRules()?.[name] ?? null;
  }
}
