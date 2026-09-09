#!/usr/bin/env node
import { startServer } from './server.js';

startServer().catch((err) => {
  console.error('imagetosvg failed to start:', err);
  process.exit(1);
});
