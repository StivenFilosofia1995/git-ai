import { createClient } from '@supabase/supabase-js'

const DEFAULT_SUPABASE_URL = 'https://zvxaaofqtbyichsllonc.supabase.co'
const DEFAULT_SUPABASE_ANON_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp2eGFhb2ZxdGJ5aWNoc2xsb25jIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYzMDQxMjUsImV4cCI6MjA5MTg4MDEyNX0.WJ8v8mmbgPjPks6XJ5_oqHcVWDAngTfnpqUwrVWmiYI'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? DEFAULT_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? DEFAULT_SUPABASE_ANON_KEY

if (!import.meta.env.VITE_SUPABASE_URL || !import.meta.env.VITE_SUPABASE_ANON_KEY) {
  console.warn('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY, using default public config')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
