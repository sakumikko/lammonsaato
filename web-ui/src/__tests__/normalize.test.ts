/**
 * Unit tests for normalization functions used in multi-entity graph.
 *
 * TDD: These tests are written BEFORE implementation.
 * They should FAIL until the functions are implemented.
 *
 * Note: These tests require a test runner like Vitest to be configured.
 * For now, they serve as documentation and will be executed once
 * Vitest is added to the project.
 */

import { describe, it, expect } from 'vitest';
import { normalize, denormalize } from '@/hooks/useHistoryData';

describe('normalize', () => {
  it('normalizes value at min to 0', () => {
    expect(normalize(20, 20, 65)).toBe(0);
  });

  it('normalizes value at max to 100', () => {
    expect(normalize(65, 20, 65)).toBe(100);
  });

  it('normalizes midpoint value to 50', () => {
    expect(normalize(42.5, 20, 65)).toBe(50);
  });

  it('handles negative ranges correctly', () => {
    // PID sum range: -20 to +20
    expect(normalize(-20, -20, 20)).toBe(0);
    expect(normalize(0, -20, 20)).toBe(50);
    expect(normalize(20, -20, 20)).toBe(100);
  });

  it('handles delta temperature range', () => {
    // Delta range: -10 to +10
    expect(normalize(-10, -10, 10)).toBe(0);
    expect(normalize(0, -10, 10)).toBe(50);
    expect(normalize(10, -10, 10)).toBe(100);
    expect(normalize(-5, -10, 10)).toBe(25);
    expect(normalize(5, -10, 10)).toBe(75);
  });

  it('handles integral range with asymmetric values', () => {
    // Integral range: -300 to +100
    expect(normalize(-300, -300, 100)).toBe(0);
    expect(normalize(100, -300, 100)).toBe(100);
    expect(normalize(-100, -300, 100)).toBe(50); // midpoint of -300 to +100 is -100
  });

  it('clamps values below min to 0', () => {
    expect(normalize(10, 20, 65)).toBe(0);
    expect(normalize(-50, -20, 20)).toBe(0);
  });

  it('clamps values above max to 100', () => {
    expect(normalize(80, 20, 65)).toBe(100);
    expect(normalize(50, -20, 20)).toBe(100);
  });

  it('returns 50 when min equals max (avoid division by zero)', () => {
    expect(normalize(50, 50, 50)).toBe(50);
  });
});

describe('denormalize', () => {
  it('denormalizes 0 to min value', () => {
    expect(denormalize(0, 20, 65)).toBe(20);
  });

  it('denormalizes 100 to max value', () => {
    expect(denormalize(100, 20, 65)).toBe(65);
  });

  it('denormalizes 50 to midpoint', () => {
    expect(denormalize(50, 20, 65)).toBe(42.5);
  });

  it('handles negative ranges correctly', () => {
    expect(denormalize(0, -20, 20)).toBe(-20);
    expect(denormalize(50, -20, 20)).toBe(0);
    expect(denormalize(100, -20, 20)).toBe(20);
  });

  it('handles delta temperature range', () => {
    expect(denormalize(0, -10, 10)).toBe(-10);
    expect(denormalize(25, -10, 10)).toBe(-5);
    expect(denormalize(50, -10, 10)).toBe(0);
    expect(denormalize(75, -10, 10)).toBe(5);
    expect(denormalize(100, -10, 10)).toBe(10);
  });

  it('is inverse of normalize', () => {
    const testCases = [
      { value: 30, min: 20, max: 65 },
      { value: -5, min: -20, max: 20 },
      { value: -150, min: -300, max: 100 },
      { value: 3.5, min: -10, max: 10 },
    ];

    for (const { value, min, max } of testCases) {
      const normalized = normalize(value, min, max);
      const denormalized = denormalize(normalized, min, max);
      expect(denormalized).toBeCloseTo(value, 5);
    }
  });
});

describe('entity preset ranges', () => {
  // Test that our preset ranges make sense

  it('PID sum range captures realistic values', () => {
    // User confirmed -20 to +20 as realistic range
    const min = -20;
    const max = 20;

    // Current observed value: -0.03
    const normalizedCurrent = normalize(-0.03, min, max);
    expect(normalizedCurrent).toBeCloseTo(49.925, 1); // Close to 50% (neutral)

    // When heater should start: < -10
    const normalizedStart = normalize(-10, min, max);
    expect(normalizedStart).toBe(25); // At 25% mark

    // Stop threshold: 0
    const normalizedStop = normalize(0, min, max);
    expect(normalizedStop).toBe(50); // At 50% mark
  });

  it('supply temperature range makes sense', () => {
    const min = 20;
    const max = 65;

    // Typical winter supply temp: 50°C
    const normalized = normalize(50, min, max);
    expect(normalized).toBeCloseTo(66.67, 1);

    // Summer supply temp: 30°C
    const normalizedSummer = normalize(30, min, max);
    expect(normalizedSummer).toBeCloseTo(22.22, 1);
  });

  it('heating integral range makes sense', () => {
    const min = -300;
    const max = 100;

    // Current observed: -150
    const normalized = normalize(-150, min, max);
    expect(normalized).toBeCloseTo(37.5, 1);

    // Neutral point (0)
    const normalizedNeutral = normalize(0, min, max);
    expect(normalizedNeutral).toBeCloseTo(75, 1);
  });
});
