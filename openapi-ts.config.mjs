/** @type {import('@hey-api/openapi-ts').UserConfig} */
export default {
  input: 'packages/api-client/openapi.json',
  output: {
    path: 'packages/api-client/src/generated',
    tsConfigPath: 'packages/api-client/tsconfig.json',
  },
  plugins: [
    { name: '@hey-api/client-fetch', baseUrl: false },
    '@hey-api/typescript',
    '@hey-api/sdk',
  ],
}
