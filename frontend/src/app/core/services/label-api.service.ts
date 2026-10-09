import { HttpClient, HttpEvent } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { FieldName, LabelExtractionResponse, TrafficLightRule } from '../models/extraction.model';

const EXTRACT_ENDPOINT = '/api/v1/labels/extract';
const TRAFFIC_LIGHT_CONFIG_ENDPOINT = '/api/v1/traffic-light/config';

@Injectable({ providedIn: 'root' })
export class LabelApiService {
  constructor(private readonly http: HttpClient) {}

  /** Emite eventos de progreso (subida) y, al final, la respuesta: permite
   *  distinguir "uploading" (subiendo bytes) de "processing" (esperando al OCR).
   *  El timeout de 30 s y la normalización de errores los aplica errorInterceptor. */
  extractLabel(file: File): Observable<HttpEvent<LabelExtractionResponse>> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post<LabelExtractionResponse>(EXTRACT_ENDPOINT, formData, {
      reportProgress: true,
      observe: 'events'
    });
  }

  getTrafficLightConfig(): Observable<Record<FieldName, TrafficLightRule>> {
    return this.http.get<Record<FieldName, TrafficLightRule>>(TRAFFIC_LIGHT_CONFIG_ENDPOINT);
  }
}
