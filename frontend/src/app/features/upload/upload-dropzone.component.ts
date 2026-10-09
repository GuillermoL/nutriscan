import { Component, DestroyRef, inject, input, output, signal } from '@angular/core';

export const ACCEPTED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'] as const;
export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

/** Validación de cliente: misma regla que el backend, para no subir lo que el servidor rechazaría. */
export function validateSelectedFile(file: File): string | null {
  if (!ACCEPTED_MIME_TYPES.includes(file.type as (typeof ACCEPTED_MIME_TYPES)[number])) {
    return 'Formato no admitido. Sube una foto en JPG, PNG o WEBP, o un PDF.';
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return 'El archivo supera el límite de 10 MB. Comprime la imagen e inténtalo de nuevo.';
  }
  return null;
}

@Component({
  selector: 'app-upload-dropzone',
  standalone: true,
  templateUrl: './upload-dropzone.component.html',
  styleUrl: './upload-dropzone.component.css'
})
export class UploadDropzoneComponent {
  readonly disabled = input(false);
  readonly analyze = output<File>();

  readonly selectedFile = signal<File | null>(null);
  readonly previewUrl = signal<string | null>(null);
  readonly validationError = signal<string | null>(null);
  readonly isDragOver = signal(false);

  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    this.destroyRef.onDestroy(() => this.revokePreview());
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    if (!this.disabled()) {
      this.isDragOver.set(true);
    }
  }

  onDragLeave(): void {
    this.isDragOver.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(false);
    if (this.disabled()) {
      return;
    }
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      this.setFile(file);
    }
  }

  onFileInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      this.setFile(file);
    }
    input.value = '';
  }

  clear(): void {
    this.revokePreview();
    this.selectedFile.set(null);
    this.previewUrl.set(null);
    this.validationError.set(null);
  }

  confirmAnalyze(): void {
    const file = this.selectedFile();
    if (file) {
      this.analyze.emit(file);
    }
  }

  private setFile(file: File): void {
    const error = validateSelectedFile(file);
    this.revokePreview();

    if (error) {
      this.selectedFile.set(null);
      this.previewUrl.set(null);
      this.validationError.set(error);
      return;
    }

    this.validationError.set(null);
    this.selectedFile.set(file);
    this.previewUrl.set(file.type === 'application/pdf' ? null : URL.createObjectURL(file));
  }

  private revokePreview(): void {
    const url = this.previewUrl();
    if (url) {
      URL.revokeObjectURL(url);
    }
  }
}
