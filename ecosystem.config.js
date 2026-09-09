const fs = require('fs');
const path = require('path');

let gunicornBin = path.join(__dirname, '.venv/bin/gunicorn');
if (!fs.existsSync(gunicornBin)) {
  gunicornBin = path.join(__dirname, 'venv/bin/gunicorn');
}
if (!fs.existsSync(gunicornBin)) {
  gunicornBin = 'gunicorn';
}

const port = process.env.PORT || 5050;

module.exports = {
  apps: [
    {
      name: "absen-seminar",
      script: gunicornBin,
      args: `--workers 3 --bind 0.0.0.0:${port} wsgi:app`,
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_memory_restart: "300M",
      env: {
        PORT: port,
        FLASK_ENV: "production"
      }
    }
  ]
};
