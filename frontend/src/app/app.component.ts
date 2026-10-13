import { HttpEventType } from '@angular/common/http';
import { Component, signal } from '@angular/core';

import { ApiErrorDetail, LabelExtractionResponse, NUTRITION_FIELD_NAMES } from './core/models/extraction.model';
import { LabelApiService } from './core/services/label-api.service';
import { ResultCardComponent } from './features/result/result-card.component';
import { UploadDropzoneComponent } from './features/upload/upload-dropzone.component';

export type AppState = 'idle' | 'uploading' | 'processing' | 'success' | 'partial' | 'error';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [UploadDropzoneComponent, ResultCardComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent {
  readonly state = signal<AppState>('idle');
  readonly result = signal<LabelExtractionResponse | null>(null);
  readonly error = signal<ApiErrorDetail | null>(null);

  constructor(private readonly api: LabelApiService) {}

  get isBusy(): boolean {
    const state = this.state();
    return state === 'uploading' || state === 'processing';
  }

  analyze(file: File): void {
    this.state.set('uploading');
    this.error.set(null);
    this.result.set(null);

    this.api.extractLabel(file).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress) {
          this.state.set(event.total && event.loaded >= event.total ? 'processing' : 'uploading');
        } else if (event.type === HttpEventType.ResponseHeader) {
          this.state.set('processing');
        } else if (event.type === HttpEventType.Response && event.body) {
          this.handleSuccess(event.body);
        }
      },
      error: (err: ApiErrorDetail) => {
        this.error.set(err);
        this.state.set('error');
      }
    });
  }

  retry(): void {
    this.state.set('idle');
    this.error.set(null);
    this.result.set(null);
  }

  private handleSuccess(response: LabelExtractionResponse): void {
    this.result.set(response);
    const allFound = NUTRITION_FIELD_NAMES.every((name) => response.fields[name].status !== 'not_found');
    this.state.set(allFound ? 'success' : 'partial');
  }
}
