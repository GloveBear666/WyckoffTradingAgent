import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react(), {
    name: 'selfhost-entry',
    transformIndexHtml: { order: 'pre', handler: () => `<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width,initial-scale=1" />
      <meta name="theme-color" content="#111817" /><title>Wyckoff Crypto · 研究工作台</title></head>
      <body><div id="root"></div><script type="module" src="/src/selfhost/main.tsx"></script></body></html>`, },
  }],
  publicDir: false,
  build: { outDir: 'dist-selfhost' },
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
