import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['src/**/*.property.spec.ts', 'src/**/*.spec.ts'],
    globals: true,
  },
});
