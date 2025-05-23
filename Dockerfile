FROM python:3.10-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv && . /opt/venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

FROM python:3.10-slim
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY . .
EXPOSE 8000
CMD ["streamlit", "run", "temp_code.py", "--server.port=8000", "--server.address=0.0.0.0"]