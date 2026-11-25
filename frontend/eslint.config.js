import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default defineConfig([
  globalIgnores(['dist', 'coverage', 'src/api/generated']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.strictTypeChecked,
      tseslint.configs.stylisticTypeChecked,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // Brief rule: UI components never call fetch directly. Only src/api may.
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: 'Use the typed client in src/api instead of calling fetch.' },
      ],
    },
  },
  {
    files: ['src/api/**/*.ts', '**/*.test.{ts,tsx}', 'src/test/**/*.ts'],
    rules: { 'no-restricted-globals': 'off' },
  },
  {
    // shadcn-generated components export variants next to components.
    files: ['src/components/ui/**/*.tsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
])
