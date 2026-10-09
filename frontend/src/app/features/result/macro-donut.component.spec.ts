import { buildDonutSegments } from './macro-donut.component';

describe('buildDonutSegments', () => {
  it('reparte proporcionalmente al valor de cada parte', () => {
    const segments = buildDonutSegments(
      [
        { name: 'a', value: 50, color: 'red' },
        { name: 'b', value: 50, color: 'blue' }
      ],
      100
    );
    expect(segments[0].percent).toBe(50);
    expect(segments[1].percent).toBe(50);
  });

  it('cuando todas las partes son 0 no reparte ninguna porción', () => {
    const segments = buildDonutSegments(
      [
        { name: 'a', value: 0, color: 'red' },
        { name: 'b', value: 0, color: 'blue' }
      ],
      100
    );
    expect(segments.every((s) => s.percent === 0)).toBe(true);
  });

  it('acumula el dashOffset en el orden de las partes', () => {
    const segments = buildDonutSegments(
      [
        { name: 'a', value: 25, color: 'red' },
        { name: 'b', value: 75, color: 'blue' }
      ],
      100
    );
    expect(segments[0].dashOffset).toBe(0);
    expect(segments[1].dashOffset).toBe(-25);
  });
});
