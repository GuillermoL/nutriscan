import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { fakeAsync, TestBed, tick } from '@angular/core/testing';

import { ApiErrorDetail } from '../models/extraction.model';
import { errorInterceptor } from './error.interceptor';

describe('errorInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([errorInterceptor])), provideHttpClientTesting()]
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('deja pasar una respuesta correcta sin modificarla', () => {
    let received: unknown;
    http.get('/api/v1/traffic-light/config').subscribe((value) => (received = value));

    httpMock.expectOne('/api/v1/traffic-light/config').flush({ ok: true });

    expect(received).toEqual({ ok: true });
  });

  it('propaga el error de dominio del backend tal cual', () => {
    let error: ApiErrorDetail | undefined;
    http.get('/api/v1/labels/extract').subscribe({ error: (err) => (error = err) });

    httpMock
      .expectOne('/api/v1/labels/extract')
      .flush(
        { error: { code: 'NO_NUTRITION_TABLE', message: 'No se encontró tabla.', hint: 'Encuadra mejor.' } },
        { status: 422, statusText: 'Unprocessable Entity' }
      );

    expect(error).toEqual({ code: 'NO_NUTRITION_TABLE', message: 'No se encontró tabla.', hint: 'Encuadra mejor.' });
  });

  it('normaliza un fallo de red como NETWORK_ERROR', () => {
    let error: ApiErrorDetail | undefined;
    http.get('/api/v1/labels/extract').subscribe({ error: (err) => (error = err) });

    httpMock.expectOne('/api/v1/labels/extract').error(new ProgressEvent('error'), { status: 0 });

    expect(error?.code).toBe('NETWORK_ERROR');
  });

  it('normaliza una respuesta que tarda más de 30 s como TIMEOUT', fakeAsync(() => {
    let error: ApiErrorDetail | undefined;
    http.get('/api/v1/labels/extract').subscribe({ error: (err) => (error = err) });

    tick(30_001);

    expect(error?.code).toBe('TIMEOUT');
    httpMock.expectOne('/api/v1/labels/extract');
  }));
});
