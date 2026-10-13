import { HttpEventType, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { LabelExtractionResponse } from '../models/extraction.model';
import { LabelApiService } from './label-api.service';

describe('LabelApiService', () => {
  let service: LabelApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()]
    });
    service = TestBed.inject(LabelApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('envía el fichero como multipart y emite la respuesta final', () => {
    const file = new File(['contenido'], 'etiqueta.jpg', { type: 'image/jpeg' });
    const response = {
      document_id: 'abc',
      basis: 'per_100g',
      fields: {},
      traffic_light: {},
      overall_traffic_light: null,
      checks: [],
      warnings: [],
      extractor: 'tesseract-rules@1.0',
      processing_ms: 10
    } as unknown as LabelExtractionResponse;

    let received: LabelExtractionResponse | undefined;
    service.extractLabel(file).subscribe((event) => {
      if (event.type === HttpEventType.Response) {
        received = event.body ?? undefined;
      }
    });

    const req = httpMock.expectOne('/api/v1/labels/extract');
    expect(req.request.method).toBe('POST');
    expect(req.request.body instanceof FormData).toBe(true);
    req.flush(response);

    expect(received).toEqual(response);
  });
});
