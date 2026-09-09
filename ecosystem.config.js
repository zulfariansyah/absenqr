const fs = require('fs');
const path = require('path');

let pythonBin = path.join(__dirname, '.venv/bin/python3');
if (!fs.existsSync(pythonBin)) {
  pythonBin = path.join(__dirname, '.venv/bin/python');
}
if (!fs.existsSync(pythonBin)) {
  pythonBin = path.join(__dirname, 'venv/bin/python3');
}
if (!fs.existsSync(pythonBin)) {
  pythonBin = 'python3';
}

const port = process.env.PORT || 5002;

module.exports = {
  apps: [
    {
      name: "absen-seminar",
      script: "app.py",
      interpreter: pythonBin,
      exec_mode: "fork",
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "300M",
      env: {
        PORT: port,
        PYTHONUNBUFFERED: "1",
        FLASK_ENV: "production"
      }
    }
  ]
};
