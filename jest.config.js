module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/tests/frontend/setup.js'],
  testMatch: ['**/tests/frontend/**/*.test.js'],
  collectCoverageFrom: [
    'src/survey/static/script.js',
    '!**/node_modules/**',
    '!**/tests/**'
  ],
  coverageReporters: ['text', 'html', 'lcov'],
  coverageDirectory: 'coverage-frontend',
  coverageThreshold: {
    global: {
      statements: 50,
      branches: 40,
      functions: 50,
      lines: 50
    }
  },
  transform: {
    '^.+\\.js$': 'babel-jest'
  }
};

