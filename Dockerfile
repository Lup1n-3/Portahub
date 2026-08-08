FROM python:3.11-slim

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Asegura que la carpeta está creada y con permisos
RUN mkdir -p static/images && chmod -R 777 static

EXPOSE 5000
CMD ["flask", "run"]
