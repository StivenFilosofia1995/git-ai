import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'co.eterea.cultura',
  appName: 'Cultura ETÉREA',
  webDir: 'dist',
  server: {
    // Carga siempre desde la web en vivo — cualquier cambio al sitio
    // se refleja en la app automáticamente sin actualizar Play Store
    url: 'https://www.culturaetereamed.com',
    cleartext: false,
  },
  android: {
    buildOptions: {
      keystorePath: undefined,
      keystorePassword: undefined,
      keystoreAlias: undefined,
      keystoreAliasPassword: undefined,
    },
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#0f0a1e',
      showSpinner: false,
    },
  },
}

export default config
