/// <reference types="vite/client" />

// Environment variables
interface ImportMetaEnv {
  readonly VITE_HA_URL?: string;
  readonly VITE_HA_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Global variables injected by HA add-on runtime
declare global {
  interface Window {
    __INGRESS_PATH__?: string;
    __SUPERVISOR_TOKEN__?: string;
  }
}
