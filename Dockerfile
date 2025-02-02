# Use python as the base image
FROM python:3.11

# Set the working directory in the container
WORKDIR /app

# Abhängigkeiten installieren
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY app.py /app/app.py

ENV PORT=4000

# Expose the specified port
EXPOSE $PORT

# Standardkommando
CMD ["python", "app.py"]