import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AppComponent } from './app.component';

describe('AppComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()]
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  function createAndFlushRules() {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    httpMock.expectOne('/api/v1/traffic-light/config').flush({});
    return fixture;
  }

  it('se crea y empieza en estado idle', () => {
    const fixture = createAndFlushRules();
    expect(fixture.componentInstance.state()).toBe('idle');
  });

  it('muestra el título NutriScan', () => {
    const fixture = createAndFlushRules();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('NutriScan');
  });

  it('vuelve a idle y limpia el error al reintentar', () => {
    const fixture = createAndFlushRules();
    const app = fixture.componentInstance;
    app.error.set({ code: 'NO_NUTRITION_TABLE', message: 'x', hint: 'y' });
    app.state.set('error');

    app.retry();

    expect(app.state()).toBe('idle');
    expect(app.error()).toBeNull();
  });
});
