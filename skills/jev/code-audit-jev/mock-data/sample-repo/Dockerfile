# VULN supply_chain / insecure_configuration: floating base, pipe to shell, runs as root
FROM python:3.12
RUN curl -sSL https://install.example.com/tool.sh | sh
COPY . /app
WORKDIR /app
CMD ["python", "app.py"]
