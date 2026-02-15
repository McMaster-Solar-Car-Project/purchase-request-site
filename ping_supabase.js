// Quick Supabase ping test
require('dotenv').config();

(async () => {
  try {
    console.log('Starting Supabase database ping...');
    
    // Check if we have the required environment variables
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_ANON_KEY;
    
    if (!supabaseUrl || !supabaseKey) {
      console.error('Missing SUPABASE_URL or SUPABASE_ANON_KEY in environment variables');
      process.exit(1);
    }
    
    console.log('Environment variables found, connecting...');

    // Import Supabase client
    const { createClient } = require('@supabase/supabase-js');
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Ping by querying the users table
    const { data, error } = await supabase
      .from('users')
      .select('id')
      .limit(1);

    if (error) {
      console.error('Supabase query error:', error.message);
      throw error;
    }

    console.log('✅ Supabase ping successful!');
    console.log('Query result:', data ? `Found ${data.length} record(s)` : 'No data returned');
    console.log('Ping completed at:', new Date().toISOString());
    
  } catch (err) {
    console.error('❌ Error pinging Supabase:', err.message);
    process.exit(1);
  }
})();