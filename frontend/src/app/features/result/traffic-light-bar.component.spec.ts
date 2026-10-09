import { ComponentFixture, TestBed } from '@angular/core/testing';

import { TrafficLightRule } from '../../core/models/extraction.model';
import { computeBands, computeScaleMax, TrafficLightBarComponent } from './traffic-light-bar.component';

const FAT_RULE: TrafficLightRule = {
  direction: 'lower_is_better',
  green_max: 3.0,
  red_min: 17.5,
  green_min: null,
  red_max: null
};

const PROTEIN_RULE: TrafficLightRule = {
  direction: 'higher_is_better',
  green_min: 10.0,
  red_max: 3.0,
  green_max: null,
  red_min: null
};

describe('computeScaleMax / computeBands (funciones puras)', () => {
  it('ordena las bandas verde-ámbar-rojo de izquierda a derecha para lower_is_better', () => {
    const scaleMax = computeScaleMax(FAT_RULE, 21.0);
    const bands = computeBands(FAT_RULE, scaleMax)!;
    expect(bands.green.left).toBe(0);
    expect(bands.amber.left).toBeCloseTo(bands.green.left + bands.green.width, 5);
    expect(bands.red.left).toBeCloseTo(bands.amber.left + bands.amber.width, 5);
  });

  it('ordena las bandas rojo-ámbar-verde de izquierda a derecha para higher_is_better', () => {
    const scaleMax = computeScaleMax(PROTEIN_RULE, 6.0);
    const bands = computeBands(PROTEIN_RULE, scaleMax)!;
    expect(bands.red.left).toBe(0);
    expect(bands.amber.left).toBeCloseTo(bands.red.left + bands.red.width, 5);
    expect(bands.green.left).toBeCloseTo(bands.amber.left + bands.amber.width, 5);
  });

  it('sin regla no hay bandas', () => {
    expect(computeBands(null, 10)).toBeNull();
  });
});

describe('TrafficLightBarComponent', () => {
  let fixture: ComponentFixture<TrafficLightBarComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [TrafficLightBarComponent] });
    fixture = TestBed.createComponent(TrafficLightBarComponent);
  });

  it('no dibuja bandas ni marcador cuando el campo es not_found', () => {
    fixture.componentRef.setInput('status', 'not_found');
    fixture.componentRef.setInput('value', null);
    fixture.componentRef.setInput('rule', FAT_RULE);
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('.bar__track')).toBeNull();
    expect(el.querySelector('.bar--not-found')).not.toBeNull();
  });

  it('marca el contenedor como doubtful cuando el estado es doubtful', () => {
    fixture.componentRef.setInput('status', 'doubtful');
    fixture.componentRef.setInput('value', 21.0);
    fixture.componentRef.setInput('color', 'red');
    fixture.componentRef.setInput('rule', FAT_RULE);
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.querySelector('.bar--doubtful')).not.toBeNull();
    expect(el.querySelector('.bar__marker')).not.toBeNull();
  });

  it('muestra un guion cuando no hay valor', () => {
    fixture.componentRef.setInput('status', 'not_found');
    fixture.componentRef.setInput('value', null);
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.textContent).toContain('—');
  });
});
