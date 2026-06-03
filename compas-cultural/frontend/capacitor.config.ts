import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'co.eterea.cultura',
  appName: 'Cultura ETÉREA',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
    // En desarrollo apunta al servidor local; en prod usa el bundle
    // url: 'http://192.168.x.x:5173',  // ← descomentar para live-reload
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
