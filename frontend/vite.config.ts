import path from 'node:path'
import os from 'node:os'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const host = process.env.TAURI_DEV_HOST
const isTauri = Boolean(process.env.TAURI_ENV_PLATFORM)
const rootDir = path.dirname(fileURLToPath(import.meta.url))
const manifest = JSON.parse(
  readFileSync(path.resolve(rootDir, '../version.json'), 'utf-8'),
) as { backend_port?: number }
const backendPort = Number(manifest.backend_port ?? 18080)
const backendUrl = `http://127.0.0.1:${backendPort}`

// Keep Vite dependency cache outside Dropbox to avoid EBUSY on rename during sync.
const viteCacheDir = process.env.LOCALAPPDATA
  ? path.join(process.env.LOCALAPPDATA, 'ShowMediaIntakeTool', 'vite-cache')
  : path.join(os.tmpdir(), 'show-media-intake-vite')

// https://vite.dev/config/
export default defineConfig({
  cacheDir: viteCacheDir,
  plugins: [react()],
  define: {
    __BACKEND_PORT__: JSON.stringify(backendPort),
  },
  resolve: {
    alias: isTauri
      ? {}
      : {
          '@tauri-apps/plugin-dialog': path.resolve(
            rootDir,
            'src/lib/stubs/tauri-plugin-dialog.ts',
          ),
        },
  },
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? { protocol: 'ws', host, port: 1421 }
      : undefined,
    watch: {
      ignored: ['**/src-tauri/**'],
    },
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY ?? backendUrl,
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
