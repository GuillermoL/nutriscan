import { DecimalPipe } from '@angular/common';
import { Component, computed, input } from '@angular/core';

import {
  FIELD_LABELS,
  FieldName,
  LabelExtractionResponse,
  NUTRITION_FIELD_NAMES,
  TrafficLightColor
} from '../../core/models/extraction.model';

const OVERALL_LABEL: Record<TrafficLightColor, string> = {
  green: 'Saludable',
  amber: 'Moderado',
  red: 'Poco saludable'
};

@Component({
  selector: 'app-result-card',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './result-card.component.html',
  styleUrl: './result-card.component.css'
})
export class ResultCardComponent {
  readonly result = input.required<LabelExtractionResponse>();

  readonly fieldNames = NUTRITION_FIELD_NAMES;
  readonly fieldLabels = FIELD_LABELS;

  readonly overallColor = computed<TrafficLightColor | null>(() => this.result().overall_traffic_light);
  readonly overallLabel = computed(() => {
    const color = this.overallColor();
    return color ? OVERALL_LABEL[color] : 'Sin valorar';
  });

  valueFor(name: FieldName): number | null {
    return this.result().fields[name].value;
  }

  unitFor(name: FieldName): string {
    return this.result().fields[name].unit;
  }
}
