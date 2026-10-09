import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError, timeout } from 'rxjs';

import { ApiErrorDetail, ApiErrorResponse } from '../models/extraction.model';

const REQUEST_TIMEOUT_MS = 30_000;

/** Traduce cualquier fallo HTTP (del backend, de red o por timeout) al mismo
 *  shape {code, message, hint}, para que los componentes no distingan el origen. */
export const errorInterceptor: HttpInterceptorFn = (req, next) =>
  next(req).pipe(
    timeout(REQUEST_TIMEOUT_MS),
    catchError((error: unknown) => throwError(() => toAppError(error)))
  );

function toAppError(error: unknown): ApiErrorDetail {
  if (error instanceof HttpErrorResponse) {
    const body = error.error as ApiErrorResponse | null;
    if (body?.error) {
      return body.error;
    }
    if (error.status === 0) {
      return {
        code: 'NETWORK_ERROR',
        message: 'No se ha podido conectar con el servidor.',
        hint: 'Comprueba tu conexión e inténtalo de nuevo.'
      };
    }
    return {
      code: 'INTERNAL_ERROR',
      message: 'Ha ocurrido un error inesperado.',
      hint: 'Inténtalo de nuevo en unos segundos.'
    };
  }

  return {
    code: 'TIMEOUT',
    message: 'La petición ha tardado demasiado.',
    hint: 'Comprueba tu conexión e inténtalo de nuevo.'
  };
}
