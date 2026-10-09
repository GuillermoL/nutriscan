import { DecimalPipe } from '@angular/common';
import { Component, computed, input } from '@angular/core';

import { FIELD_LABELS } from '../../core/models/extraction.model';

const RADIUS = 60;
const STROKE_WIDTH = 18;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const GAP_LENGTH = 3; // separación visual entre segmentos (equivalente al "surface gap" de 2px)

export interface DonutPart {
  name: string;
  value: number;
  color: string;
}

export interface DonutSegment extends DonutPart {
  percent: number;
  dashArray: string;
  dashOffset: number;
}

/** Pura y testeable sin SVG: reparte la circunferencia entre partes proporcionalmente a su valor. */
export function buildDonutSegments(parts: DonutPart[], circumference: number): DonutSegment[] {
  const total = parts.reduce((sum, part) => sum + part.value, 0);
  if (total <= 0) {
    return parts.map((part) => ({ ...part, percent: 0, dashArray: `0 ${circumference}`, dashOffset: 0 }));
  }

  let cumulative = 0;
  return parts.map((part) => {
    const percent = (part.value / total) * 100;
    const rawLength = (part.value / total) * circumference;
    const length = Math.max(rawLength - GAP_LENGTH, 0);
    const dashOffset = -cumulative;
    cumulative += rawLength;
    return { ...part, percent, dashArray: `${length} ${circumference - length}`, dashOffset };
  });
}

@Component({
  selector: 'app-macro-donut',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './macro-donut.component.html',
  styleUrl: './macro-donut.component.css'
})
export class MacroDonutComponent {
  readonly fatG = input<number | null>(null);
  readonly carbsG = input<number | null>(null);
  readonly proteinG = input<number | null>(null);
  readonly kcal = input<number | null>(null);

  readonly radius = RADIUS;
  readonly strokeWidth = STROKE_WIDTH;

  readonly segments = computed<DonutSegment[]>(() =>
    buildDonutSegments(
      [
        { name: FIELD_LABELS['fat_g'], value: this.fatG() ?? 0, color: 'var(--series-fat)' },
        { name: FIELD_LABELS['carbohydrates_g'], value: this.carbsG() ?? 0, color: 'var(--series-carbs)' },
        { name: FIELD_LABELS['protein_g'], value: this.proteinG() ?? 0, color: 'var(--series-protein)' }
      ],
      CIRCUMFERENCE
    )
  );

  readonly hasData = computed(() => this.segments().some((segment) => segment.value > 0));
}
