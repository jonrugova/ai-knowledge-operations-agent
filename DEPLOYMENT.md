# Deployment preparation

## Development

Run the FastAPI backend:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Run the React frontend in a separate terminal:

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

## Production preparation

Build the React frontend:

```bash
cd frontend
npm run build
```

Set these backend environment variables:

- `APP_ENV=production`
- `SESSION_SECRET`
- `ADMIN_PASSWORD`
- `EMPLOYEE_PASSWORD`
- `FRONTEND_ORIGIN` when cross-origin browser access is required
- `PORT` when the service should not use port 8000

Start the single FastAPI service:

```bash
python start.py
```