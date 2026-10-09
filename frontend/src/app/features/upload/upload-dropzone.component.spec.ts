import { MAX_FILE_SIZE_BYTES, validateSelectedFile } from './upload-dropzone.component';

function makeFile(type: string, sizeBytes: number): File {
  return new File([new Uint8Array(sizeBytes)], 'etiqueta', { type });
}

describe('validateSelectedFile', () => {
  it('acepta JPG, PNG, WEBP y PDF dentro del límite de tamaño', () => {
    for (const type of ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']) {
      expect(validateSelectedFile(makeFile(type, 1024))).toBeNull();
    }
  });

  it('rechaza un tipo no admitido', () => {
    const error = validateSelectedFile(makeFile('text/plain', 1024));
    expect(error).toContain('Formato no admitido');
  });

  it('rechaza un archivo que supera el límite de tamaño', () => {
    const error = validateSelectedFile(makeFile('image/jpeg', MAX_FILE_SIZE_BYTES + 1));
    expect(error).toContain('10 MB');
  });

  it('acepta un archivo justo en el límite de tamaño', () => {
    expect(validateSelectedFile(makeFile('image/jpeg', MAX_FILE_SIZE_BYTES))).toBeNull();
  });
});
