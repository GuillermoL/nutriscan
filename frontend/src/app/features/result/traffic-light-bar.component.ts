import { Component, computed, input } from '@angular/core';

import { FieldStatus, TrafficLightColor, TrafficLightRule } from '../../core/models/extraction.model';

export interface Band {
  left: number;
  width: number;
}

const STATUS_COLOR_VAR: Record<TrafficLightColor, string> = {
  green: 'var(--status-good)',
  amber: 'var(--status-warning)',
  red: 'var(--status-critical)'
};

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value));
}

/** Pura y testeable sin SVG: calcula el tamaño de escala a partir de los umbrales de la regla. */
export function computeScaleMax(rule: TrafficLightRule | null, value: number): number {
  if (!rule) {
    return Math.max(value, 1);
  }
  const reference = rule.direction === 'lower_is_better' ? rule.red_min ?? 0 : rule.green_min ?? 0;
  return Math.max(reference * 1.6, value * 1.05, 1);
}

/** Pura y testeable: las tres bandas de color se expresan como % de la escala total. */
export function computeBands(rule: TrafficLightRule | null, scaleMax: number): Record<'green' | 'amber' | 'red', Band> | null {
  if (!rule) {
    return null;
  }

  if (rule.direction === 'lower_is_better') {
    const greenMax = rule.green_max ?? 0;
    const redMin = rule.red_min ?? greenMax;
    const greenEnd = clampPercent((greenMax / scaleMax) * 100);
    const amberEnd = clampPercent((redMin / scaleMax) * 100);
    return {
      green: { left: 0, width: greenEnd },
      amber: { left: greenEnd, width: amberEnd - greenEnd },
      red: { left: amberEnd, width: 100 - amberEnd }
    };
  }

  const redMax = rule.red_max ?? 0;
  const greenMin = rule.green_min ?? redMax;
  const redEnd = clampPercent((redMax / scaleMax) * 100);
  const amberEnd = clampPercent((greenMin / scaleMax) * 100);
  return {
    red: { left: 0, width: redEnd },
    amber: { left: redEnd, width: amberEnd - redEnd },
    green: { left: amberEnd, width: 100 - amberEnd }
  };
}

@Component({
  selector: 'app-traffic-light-bar',
  standalone: true,
  templateUrl: './traffic-light-bar.component.html',
  styleUrl: './traffic-light-bar.component.css'
})
export class TrafficLightBarComponent {
  readonly label = input('');
  readonly value = input<number | null>(null);
  readonly unit = input('');
  readonly status = input.required<FieldStatus>();
  readonly color = input<TrafficLightColor | null>(null);
  readonly rule = input<TrafficLightRule | null>(null);

  readonly scaleMax = computed(() => computeScaleMax(this.rule(), this.value() ?? 0));
  readonly bands = computed(() => computeBands(this.rule(), this.scaleMax()));

  readonly markerLeft = computed(() => {
    const value = this.value();
    if (value === null) {
      return null;
    }
    return clampPercent((value / this.scaleMax()) * 100);
  });

  readonly markerColorVar = computed(() => {
    const color = this.color();
    return color ? STATUS_COLOR_VAR[color] : 'var(--status-unknown)';
  });
}
