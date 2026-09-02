module.exports = {
  apps: [
    {
      name: "absen-seminar",
      script: "venv/bin/gunicorn",
      args: "--workers 3 --bind 127.0.0.1:5000 wsgi:app",
      cwd: "./",
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "300M",
      env: {
        PORT: 5000,
        FLASK_ENV: "production"
      }
    }
  ]
};
