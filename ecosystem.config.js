module.exports = {
  apps: [
    {
      name: 'portfolio-backend',
      cwd: 'C:\\vscode\\portfolio1.6\\backend',
      script: 'C:\\vscode\\portfolio1.6\\venv\\Scripts\\uvicorn.exe',
      args: 'main:app --host 0.0.0.0 --port 8000',
      interpreter: 'none',
      watch: false,
      env: {
        PYTHONPATH: 'C:\\vscode\\portfolio1.6'
      }
    },
    {
      name: 'portfolio-web',
      cwd: 'C:\\vscode\\portfolio1.6\\web',
      script: 'node_modules\\next\\dist\\bin\\next',
      args: 'start',
      watch: false,
      env: {
        NODE_ENV: 'production',
        PORT: 3000
      }
    }
  ]
}
