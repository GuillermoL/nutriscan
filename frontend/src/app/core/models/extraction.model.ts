/** Espejo en TypeScript de la respuesta de POST /api/v1/labels/extract. */

export type FieldName = 'energy_kcal' | 'fat_g' | 'carbohydrates_g' | 'protein_g';

export const NUTRITION_FIELD_NAMES: readonly FieldName[] = [
  'energy_kcal',
  'fat_g',
  'carbohydrates_g',
  'protein_g'
];

export const FIELD_LABELS: Record<FieldName, string> = {
  energy_kcal: 'Energía',
  fat_g: 'Grasas',
  carbohydrates_g: 'Hidratos de carbono',
  protein_g: 'Proteínas'
};

export type FieldStatus = 'ok' | 'doubtful' | 'not_found';

export type TrafficLightColor = 'green' | 'amber' | 'red';

export interface NutritionField {
  value: number | null;
  unit: string;
  status: FieldStatus;
  confidence: number;
  raw_text: string | null;
  source: string | null;
  reason: string | null;
}

export interface CheckResult {
  name: string;
  passed: boolean;
  detail: string;
}

export interface LabelExtractionResponse {
  document_id: string;
  basis: string;
  fields: Record<FieldName, NutritionField>;
  traffic_light: Record<FieldName, TrafficLightColor | null>;
  overall_traffic_light: TrafficLightColor | null;
  checks: CheckResult[];
  warnings: string[];
  extractor: string;
  processing_ms: number;
}

export interface TrafficLightRule {
  direction: 'lower_is_better' | 'higher_is_better';
  green_max: number | null;
  red_min: number | null;
  green_min: number | null;
  red_max: number | null;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  hint: string;
  request_id?: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}
